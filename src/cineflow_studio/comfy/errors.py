class ComfyUIError(Exception):
    pass


class ComfyUIConnectionError(ComfyUIError):
    pass


class ComfyUIQueueError(ComfyUIError):
    pass


class ComfyUIHistoryError(ComfyUIError):
    pass


class ComfyUIUploadError(ComfyUIError):
    pass


class ComfyUIPromptFormatError(ComfyUIError):
    pass
