#!/usr/bin/env python3
"""
Save or check the IBM Quantum account of the person using this Pi.

Every demo runs without an account, on a simulator. For real IBM Quantum
computers each student creates their OWN free account at
https://quantum.cloud.ibm.com (Open Plan), creates an API key there and saves
it here (Jan, Q31). The account goes to ~/.qiskit of the user who runs this
script - the RasQberry menu runs it as the desktop user, so the menu,
notebooks and the learner's own programs all find it (Q26).

Usage:
    rq_set_qiskit_ibm_token.py            ask for the API key (and an optional
                                          instance CRN), check it, then save it
    rq_set_qiskit_ibm_token.py --check    check the saved account
    rq_set_qiskit_ibm_token.py --no-check save without checking (offline)

Exit codes: 0 saved / valid, 1 not saved / not valid, 2 IBM Quantum could not
be reached (nothing changed).
"""

import argparse
import getpass
import logging
import socket
import sys

CHANNEL = "ibm_quantum_platform"
IAM_HOST = ("iam.cloud.ibm.com", 443)
SIGNUP = "https://quantum.cloud.ibm.com"


def online():
    """
    Can IBM Cloud be reached? (DNS + TCP to the IAM endpoint, 5 s)

    Returns:
        bool: True when a connection could be made
    """
    try:
        socket.create_connection(IAM_HOST, timeout=5).close()
        return True
    except OSError:
        return False


def check(token=None, instance=None):
    """
    Log in to IBM Quantum with the given key, or with the saved account.

    Args:
        token (str): API key to check; None checks the saved account
        instance (str): optional instance CRN

    Returns:
        tuple: (ok, message)
    """
    from qiskit_ibm_runtime import QiskitRuntimeService
    # its "Loading account with the given token" warning is noise here
    logging.getLogger("qiskit_ibm_runtime").setLevel(logging.ERROR)
    try:
        if token:
            service = QiskitRuntimeService(channel=CHANNEL, token=token, instance=instance or None)
        else:
            service = QiskitRuntimeService()
        names = [b.name for b in service.backends()]
    except Exception as exc:  # the runtime raises many types; the text matters
        text = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
        return False, text[:200]
    if not names:
        return True, "Logged in. This account has no quantum computers available right now."
    more = " ..." if len(names) > 5 else ""
    return True, f"Logged in. Quantum computers available: {', '.join(names[:5])}{more}"


def ask(prompt):
    """
    input() that treats Ctrl+D / Ctrl+C as an empty answer.

    Args:
        prompt (str): the question

    Returns:
        str: the answer, stripped
    """
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def main():
    """Run the chosen action; returns the exit code."""
    parser = argparse.ArgumentParser(description="Save or check your IBM Quantum account.")
    parser.add_argument("--check", action="store_true", help="check the saved account")
    parser.add_argument("--no-check", action="store_true", help="save without checking")
    args = parser.parse_args()

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError:
        print("Qiskit is not installed for this user (qiskit-ibm-runtime missing).")
        return 1

    if args.check:
        if not QiskitRuntimeService.saved_accounts():
            print("No IBM Quantum account is saved for this user.")
            return 1
        if not online():
            print("IBM Quantum cannot be reached (no internet?), so the account was not checked.")
            return 2
        ok, msg = check()
        print(msg if ok else f"The saved account does not work: {msg}")
        return 0 if ok else 1

    print("Every demo runs without an account, on a simulator.")
    print(f"For real IBM Quantum computers, use your own free account from {SIGNUP}:")
    print("create an API key there and paste it here (it is not shown while you type).")
    print()
    try:
        token = getpass.getpass("API key (Enter = cancel): ").strip()
    except (EOFError, KeyboardInterrupt):
        token = ""
    if not token:
        print("Nothing saved.")
        return 1
    instance = ask("Instance CRN (optional, Enter = any instance of the account): ")

    if not args.no_check:
        if online():
            print("Checking the API key with IBM Quantum...")
            ok, msg = check(token, instance)
            if not ok:
                print(f"The API key was not accepted, so it was not saved: {msg}")
                return 1
            print(msg)
        elif ask("IBM Quantum cannot be reached. Save the key without checking it? (y/N) ").lower() != "y":
            print("Nothing saved.")
            return 2

    QiskitRuntimeService.save_account(
        channel=CHANNEL,
        token=token,
        instance=instance or None,
        set_as_default=True,
        overwrite=True,
    )
    print("Saved for this user. Notebooks and your own programs use it with QiskitRuntimeService().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
