from distutils.core import setup

description = '''
Module for running trial-based experiments.  Originally
adapted from the Neurobehavior package.
'''

setup(
    name='PyExperiment',
    version='0.01',
    author='Brad Buran',
    author_email='bburan@galenea.com',
    packages=[
        'experiment',
        'experiment.evaluate',
    ],
    license='LICENSE.txt',
    description=description,
    package_data = {
        'experiment': ['icons/*.png'],
    }
)
