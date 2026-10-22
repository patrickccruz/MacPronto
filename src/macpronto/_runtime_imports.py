"""Módulos usados pelo código de terceiros que roda como fonte dentro do executável.

O OpCore Simplify, o Hardware Sniffer e o macrecovery são carregados a partir da
área de trabalho (arquivos .py), não compilados. Importar aqui garante que o
Nuitka inclua no executável tudo o que eles usam da biblioteca padrão.
"""

# ruff: noqa: F401
import argparse
import binascii
import ctypes
import errno
import getpass
import gzip
import hashlib
import http.client
import importlib.util
import json
import linecache
import mmap
import os
import pathlib
import platform
import plistlib
import queue
import random
import re
import shlex
import shutil
import socket
import ssl
import string
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib

if sys.platform == "win32":
    import winreg

    import pythoncom
    import pywintypes
    import win32com.client
    import wmi
