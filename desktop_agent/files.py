"""Linux atomic rename without overwriting a concurrent destination."""
import ctypes
import errno
import os
from .client import AgentError


def move_no_replace(source, destination):
    library=ctypes.CDLL(None,use_errno=True)
    rename=getattr(library,'renameat2',None)
    if rename is None:
        raise AgentError('ATOMIC_MOVE_UNAVAILABLE')
    rename.argtypes=(ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint)
    rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(source),-100,os.fsencode(destination),1):
        code=ctypes.get_errno()
        errors={errno.EEXIST:'DESTINATION_EXISTS',errno.EXDEV:'CROSS_FILESYSTEM_MOVE_UNSUPPORTED',
                errno.ENOENT:'FILE_NOT_FOUND',errno.EACCES:'FILE_PERMISSION_DENIED',errno.EPERM:'FILE_PERMISSION_DENIED'}
        raise AgentError(errors.get(code,'FILE_MOVE_FAILED'))
