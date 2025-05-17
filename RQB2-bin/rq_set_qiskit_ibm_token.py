from qiskit_ibm_runtime import QiskitRuntimeService
import getpass
import os

# Function to get the token if not already saved

def get_token_from_service():
    try:
        service = QiskitRuntimeService()
        # Check if an active account is already available
        account_info = service.active_account()
        if account_info:
            #print("Using saved IBM Quantum account...")
            return account_info['token']  # Extract the token from the saved account
        else:
            raise Exception("No active account found.")
    except Exception as e:
        # Prompt the user to enter the token if no account is found
        #print("account_info exception", str(e))
        token = getpass.getpass(prompt="Enter your IBM Quantum token: ")
        return token

def get_token():
    # Check if a token is saved
    saved_token = get_token_from_service()
    # If there's a saved token, ask the user if they want to use it
    #print("saved_token",saved_token)
    if saved_token:
        use_saved = input("Do you want to use the saved token? (y/n): ").lower()
        if use_saved == 'y':
            print("Using previously saved token.")
            return saved_token
        else:
            # If the user chooses not to use the saved token, prompt for a new one
            print("Please enter a new token.")
            return getpass.getpass(prompt="Enter your IBM Quantum token: ")
    else:
        # If no token is saved, prompt for a new one
        return getpass.getpass(prompt="Enter your IBM Quantum token: ")


# Get channel input from user, with default value as 'ibm_quantum'
channel = input("Enter the channel (default: ibm_quantum): ") or "ibm_quantum"

# Get the token (either saved or by prompting the user)
token = get_token()

# Save the account and set as default
if token:
    QiskitRuntimeService.save_account(
        channel=channel,
        token=token,
        set_as_default=True,
        overwrite=True  # Use overwrite to update the token if needed
    )
    # Load saved credentials
    service = QiskitRuntimeService()
else:
    print("API Key is not passed Qiskit Runtime will not save the credentials")
