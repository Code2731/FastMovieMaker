from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

extensions = [
    Extension("src.utils.time_utils", ["src/utils/time_utils.py"]),
    Extension("src.services.ducking_service", ["src/services/ducking_service.py"]),
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}),
    include_dirs=[np.get_include()],
    package_dir={'': '.'}
)
