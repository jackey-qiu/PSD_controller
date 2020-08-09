import os

from distutils.core import setup

packages = ["syringedrive"]
package_data = {'syringedrive' : []}


setup(name='pySyringeDrive', version='0.1.0',
      description='Interface software for asynchronous controlling of Hamilton pumps and valves',
      long_description='FIXME',
      packages=packages,
	  package_data=package_data,
      author="Timo Fuchs",
      author_email="fuchs@physik.uni-kiel.de",
      url='FIXME',
      license='All rights reserved',
      install_requires=[
      'numpy >= 1.12',
      'scipy >= 1.0',
      'pyserial >= 3.4'],
      python_requires='>=3.5',
      classifiers=[
          'Topic :: Scientific/Engineering',
          'Development Status :: 3 - Alpha',
          'Operating System :: OS Independent',
          'Programming Language :: Python ']
      )
