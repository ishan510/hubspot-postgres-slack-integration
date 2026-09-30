"""Store only this project's HubSpot key in the macOS login Keychain."""
import getpass
import sys

SERVICE = 'acme-crm-sync'
ACCOUNT = 'hubspot-service-key'


def backend():
    # Explicitly select the native backend; never fall back to a plaintext store.
    from keyring.backends.macOS import Keyring
    return Keyring()


def load_key():
    return backend().get_password(SERVICE, ACCOUNT)


def main():
    token = getpass.getpass('Paste your HubSpot Service Key to save in Keychain (hidden): ').strip()
    if not token:
        print('No key entered. Nothing was saved.')
        return 1
    try:
        backend().set_password(SERVICE, ACCOUNT, token)
    except Exception:
        print('Could not save the key. Check that keyring is installed and your login Keychain is unlocked.')
        return 1
    print('Saved in macOS Keychain. The key was not written into the project files.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled.')
        sys.exit(1)
