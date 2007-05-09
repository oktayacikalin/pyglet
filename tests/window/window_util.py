#!/usr/bin/python
# $Id:$

from pyglet.gl import *

def draw_client_border(window):
    glClearColor(0, 0, 0, 1)
    glClear(GL_COLOR_BUFFER_BIT)
    glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, window.width, 0, window.height, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    def rect(x1, y1, x2, y2):
        glBegin(GL_POLYGON)
        glVertex2f(x1, y1)
        glVertex2f(x2, y1)
        glVertex2f(x2, y2)
        glVertex2f(x1, y2)
        glEnd()
    
    glColor3f(1, 0, 0)
    rect(-1, -1, window.width, window.height)

    glColor3f(0, 1, 0)
    rect(0, 0, window.width - 1, window.height - 1)