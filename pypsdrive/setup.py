import os

try:
    from setuptools import setup
except ImportError:
    from numpy.distutils.core import setup

packages = ["psdrive"]
package_data = {'psdrive' : []}


setup(name='pyPSDrive', version='0.1.0',
      description='Interface software for asynchronous controlling of Hamilton pumps and valves',
      long_description='FIXME',
      packages=packages,
	  package_data=package_data,
      author="Timo Fuchs",
      author_email="fuchs@physik.uni-kiel.de",
      url='FIXME',
      entry_points = {
        'console_scripts': ['PumpServer=psdrive.PumpServer:main']
      },
      license='All rights reserved',
      install_requires=[
      'numpy >= 1.12',
      'pyserial >= 3.4',
      'pytango >= 9.2',
      'pyyaml'],
      python_requires='>=3.6',
      classifiers=[
          'Topic :: Scientific/Engineering',
          'Development Status :: 3 - Alpha',
          'Operating System :: OS Independent',
          'Programming Language :: Python ']
      )
