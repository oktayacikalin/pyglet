#!/usr/bin/env python

'''
'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

from pyglet.GL.VERSION_1_1 import *
from pyglet.image import *
from pyglet.image.codecs import *

import Image

class PILImageDecoder(ImageDecoder):
    def get_file_extensions(self):
        # Only most common ones shown here
        return ['.bmp', '.cur', '.gif', '.ico', '.jpg', '.jpeg', '.pcx', '.png',
                '.tga', '.tif', '.tiff', '.xbm', '.xpm']

    def decode(self, file, filename):
        image = Image.open(file)

        # Convert bitmap and palette images to component
        if image.mode in ('1', 'P'):
            image = image.convert()

        if image.mode == 'L':
            format = GL_LUMINANCE
        elif image.mode == 'RGB':
            format = GL_RGB
        elif image.mode == 'RGBA':
            format = GL_RGBA
        else:
            assert False, 'Unknown image mode %s' % image.mode
        type = GL_UNSIGNED_BYTE

        width, height = image.size
        return RawImage(image.tostring(), width, height, format, type)

def get_decoders():
    return [PILImageDecoder()]

def get_encoders():
    return []
