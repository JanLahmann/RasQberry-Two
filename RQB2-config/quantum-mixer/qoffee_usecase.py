from typing import Optional, Annotated, Union
import html
import json
import os
from urllib.parse import quote
from pydantic import BaseModel
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import HTMLResponse, RedirectResponse
from requests_oauthlib import OAuth2Session
from quantum_mixer_backend.usecases.usecase import Usecase
from quantum_mixer_backend.usecases.usecase_data import OrderData, UsecaseData, UsecasePreferences, UsecaseBitMappingItem
from quantum_mixer_backend.usecases.utils import handle_response, get_return_type, StrEnum

class QoffeeUsecaseDrinkOptions(BaseModel):
    key: Annotated[str, 'Key for option']
    value: Annotated[str, 'Value for option']

class QoffeeUsecaseBitmappingItem(UsecaseBitMappingItem):
    key: Annotated[str, 'Key for Homeconnect API']
    options: Annotated[Optional[list[QoffeeUsecaseDrinkOptions]], 'Options for Homeconnect API']

class QoffeeUsecasePreferences(UsecasePreferences):
    selectedMachineHaId: Optional[str]
    bitMapping: Annotated[list[QoffeeUsecaseBitmappingItem], "Mapping of bit configurations to products/items"]

# Shown instead of a bare "Internal Server Error" when no Home Connect account
# is configured: the OAuth login cannot work then ("OAuth 2 MUST utilize https").
NOT_CONFIGURED_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QoffeeMaker needs a Home Connect account</title>
<style>
body {{ font-family: "IBM Plex Sans", Arial, sans-serif; background: #161616; color: #f4f4f4;
       margin: 0; padding: 48px 24px; }}
main {{ max-width: 640px; margin: 0 auto; }}
h1 {{ font-weight: 400; font-size: 32px; margin: 0 0 24px; }}
p {{ font-size: 18px; line-height: 1.5; }}
a.button {{ display: inline-block; margin: 16px 16px 0 0; padding: 14px 20px; font-size: 18px;
           text-decoration: none; color: #fff; background: #0f62fe; }}
a.button.secondary {{ background: #393939; }}
code {{ font-size: 16px; }}
</style></head>
<body><main>
<h1>QoffeeMaker needs a Home Connect account</h1>
<p>QoffeeMaker orders the measured drink from a real coffee machine through
Home Connect. This Quantum Mixer has no Home Connect account set up, so it
cannot reach a machine.</p>
<p>You can still build the circuit and measure it: the drink is only shown,
not made. Qocktail and IceQream work fully.</p>
<p>To connect a machine: create a developer account at
<code>developer.home-connect.com</code>, then {how}</p>
<a class="button" href="{skip}">Try it without a coffee machine</a>
<a class="button secondary" href="/">Back to the start page</a>
</main></body></html>
"""


class QoffeeUsecase(Usecase):

    preferences: QoffeeUsecasePreferences
    post_login_redirect: Union[str, None] = None

    def __init__(self, data: UsecaseData, preferences: QoffeeUsecasePreferences):
        super().__init__(data, preferences)

        self.client_id     = os.getenv('HOMECONNECT_CLIENT_ID')
        self.client_secret = os.getenv('HOMECONNECT_CLIENT_SECRET')
        self.base_url      = os.getenv('HOMECONNECT_BASE_URL')
        self.host_address  = os.getenv('HOST_ADDRESS')
        # Without these the OAuth login fails; Qoffee then runs as a simulation
        self.configured    = all([self.client_id, self.client_secret, self.base_url, self.host_address])
        # Optional text for the not-configured page: where this installation keeps
        # the account (e.g. a settings file), instead of the environment variables
        self.setup_hint    = os.getenv('HOMECONNECT_SETUP_HINT', '')

        # create oauth2 session
        self.session = OAuth2Session(
            client_id=self.client_id, 
            redirect_uri='{}/api/usecase/qoffee/auth/callback'.format(self.host_address),
            scope=["IdentifyAppliance", "CoffeeMaker"],
            auto_refresh_url='{}/security/oauth/token'.format(self.base_url),
            auto_refresh_kwargs={
                'client_id': self.client_id,
                'client_secret': self.client_secret
            },
            token_updater=self.set_token
        )
    
    def set_token(self, token):
        self.data.loginRequired = False
        self.token = token

    def get_preferences(self) -> QoffeeUsecasePreferences:
        return super().get_preferences()
    
    def get_preferences_schema(self):
        if not self.configured:
            return super().get_preferences_schema()
        # get all available coffee machines
        coffee_machines = self.get_coffee_machines()
        # create a new pydantic model and allow selectedMachineHaId to be only one of the coffee machines
        CoffeeMachines = StrEnum('CoffeeMachines', {'cm{}'.format(i): x['haId'] for i, x in enumerate(coffee_machines)})
        class QoffeeUsecasePreferences_(QoffeeUsecasePreferences):
            selectedMachineHaId: CoffeeMachines
        # return schema
        return QoffeeUsecasePreferences_.schema()
    
    def set_preferences(self, preferences: QoffeeUsecasePreferences) -> bool:
        worked = super().set_preferences(preferences)
        # return early
        if not worked:
            return False
        # make sure coffee machine is turned on
        if preferences.selectedMachineHaId is not None:
            self.fetch_put('/api/homeappliances/{}/settings/BSH.Common.Setting.PowerState'.format(preferences.selectedMachineHaId), {
                "data": {
                    "key": "BSH.Common.Setting.PowerState",
                    "value": "BSH.Common.EnumType.PowerState.On"
                }
            })
        return True

    def fetch_put(self, path: str, body) -> tuple[int, any]:
        response = self.session.put('{}{}'.format(self.base_url, path), json.dumps(body), headers={
            'Content-Type': 'application/json'
        })
        status, data = handle_response(response)

        if status >= 300:
            raise HTTPException(
                status_code=status,
                detail=data,
            )

        return data

    def fetch_get(self, path: str) -> tuple[int, any]:
        response = self.session.get('{}{}'.format(self.base_url, path))
        status, data = handle_response(response)

        if status >= 300:
            raise HTTPException(
                status_code=status,
                detail=data,
            )

        return data

    def get_coffee_machines(self):
        data = self.fetch_get('/api/homeappliances')
        coffee_machines = list(filter(lambda x: x['type'] == 'CoffeeMaker', data['data']['homeappliances']))
        return coffee_machines
        
    def set_endpoints(self, app: FastAPI, prefix: str):
        super().set_endpoints(app, prefix)

        @app.get('{}/auth/login'.format(prefix))
        def login(redirect: str = ''):
            if not self.configured:
                # a friendly page instead of oauthlib's InsecureTransportError (500)
                skip = '{}/auth/skip?redirect={}'.format(prefix, quote(redirect, safe=''))
                how = html.escape(self.setup_hint) if self.setup_hint else (
                    'start the Mixer with <code>HOMECONNECT_CLIENT_ID</code>, '
                    '<code>HOMECONNECT_CLIENT_SECRET</code>, <code>HOMECONNECT_BASE_URL</code> '
                    'and <code>HOST_ADDRESS</code> set.')
                return HTMLResponse(NOT_CONFIGURED_PAGE.format(skip=html.escape(skip, quote=True), how=how))
            authorization_url, _ = self.session.authorization_url(
                '{}/security/oauth/authorize'.format(self.base_url),
            )
            self.post_login_redirect = redirect
            return RedirectResponse(authorization_url)

        @app.get('{}/auth/skip'.format(prefix))
        def skip_login(request: Request, redirect: str = '') -> RedirectResponse:
            # simulation only: no login, no order button
            if not self.configured:
                self.data.loginRequired = False
                self.data.hasOrder = False
            # only redirect within this app
            local = redirect.startswith('/') and not redirect.startswith('//')
            if not (local or redirect.startswith(str(request.base_url))):
                redirect = '/'
            return RedirectResponse(redirect)

        @app.get('{}/auth/callback'.format(prefix))
        def handle_authorization_callback(request: Request, code: str = '') -> RedirectResponse: 
            token = self.session.fetch_token(
                '{}/security/oauth/token'.format(self.base_url),
                client_secret=self.client_secret,
                authorization_response=request.url._url.replace('http://', 'https://')
            )
            self.set_token(token)
            coffee_machines = self.get_coffee_machines()
            if len(coffee_machines) > 0:
                self.preferences.selectedMachineHaId = coffee_machines[0]['haId']
            return RedirectResponse(self.post_login_redirect)

        @app.post('{}/order'.format(prefix))
        async def handle_order(data: OrderData) -> get_return_type(self.handle_order):
            return self.handle_order(data)

    def handle_order(self, data: OrderData) -> bool:
        if not self.configured:
            raise HTTPException(status_code=409, detail='QoffeeMaker needs a Home Connect account to order a drink.')
        if len(data.items) != 1:
            raise RuntimeError("Unable to process other than 1 item, got {}".format(len(data.items)))

        drink_data = next(
            filter(lambda x: x.bits == data.items[0], self.preferences.bitMapping)
        )
        drink_data_key     = drink_data.key
        drink_data_options = [] if drink_data.options is None else list(map(lambda x: x.dict(), drink_data.options))

        # quickfix: homeconnect api only accepts integer values, not strings
        for option in drink_data_options:
            if option["value"].isnumeric():
                option["value"] = int(option["value"])

        self.fetch_put('/api/homeappliances/{}/programs/active'.format(self.preferences.selectedMachineHaId), {
            'data': {
                'key': drink_data_key,
                'options': drink_data_options
            }
        })

        return True

