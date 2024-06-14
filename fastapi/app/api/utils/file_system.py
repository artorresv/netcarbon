from os.path import isdir


def local_path(dir_path: str) -> str:
    if isdir(dir_path):
        return str(dir_path)
    else:
        raise NotADirectoryError(dir_path)
