class GatewayError(Exception):
    pass


class ProviderNotFoundError(GatewayError):
    def __init__(self, provider_name: str):
        super().__init__(f"Provider '{provider_name}' is not registered.")


class ProviderAuthError(GatewayError):
    pass


class ProviderAPIError(GatewayError):
    def __init__(self, provider: str, message: str, status_code: int = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")
