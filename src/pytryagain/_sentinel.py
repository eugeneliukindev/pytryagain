class _Sentinel:
    _instance: "_Sentinel | None" = None

    def __new__(cls) -> "_Sentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


# 12
_MISSING = _Sentinel()
