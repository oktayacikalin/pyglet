#!/usr/bin/env python

'''
Documentation sources for Xlib programming:

http://tronche.com/gui/x/ (specifically xlib/ and icccm/)

http://users.actcom.co.il/~choo/lupg/tutorials/xlib-programming/xlib-programming.html

'''

__docformat__ = 'restructuredtext'
__version__ = '$Id$'

from ctypes import *
from ctypes import util
import unicodedata

from pyglet.window import *
from pyglet.window.event import *
from pyglet.window.key import *
from pyglet.window.xlib.constants import *
from pyglet.window.xlib.types import *
from pyglet.window.xlib.glx.VERSION_1_4 import *

# Load X11 library, specify argtypes and restype only when necessary.
Display = c_void_p
Atom = c_ulong

path = util.find_library('X11')
if not path:
    raise ImportError('Cannot locate X11 library')
xlib = cdll.LoadLibrary(path)
xlib.XOpenDisplay.argtypes = [c_char_p]
xlib.XOpenDisplay.restype = POINTER(Display)
xlib.XInternAtom.restype = Atom
xlib.XNextEvent.argtypes = [POINTER(Display), POINTER(XEvent)]
xlib.XCheckTypedWindowEvent.argtypes = [POINTER(Display),
    c_ulong, c_int, POINTER(XEvent)]
xlib.XPutBackEvent.argtypes = [POINTER(Display), POINTER(XEvent)]

# Do we have the November 2000 UTF8 extension?
_have_utf8 = hasattr(xlib, 'Xutf8TextListToTextProperty')

class XlibException(WindowException):
    pass

class XlibWindowFactory(BaseWindowFactory):
    def __init__(self, display=None):
        super(XlibWindowFactory, self).__init__()

        self._display = xlib.XOpenDisplay(display)
        if not self._display:
            raise XlibException('Cannot connect to X server') 

    def create_config_prototype(self):
        return XlibGLConfig()

    def get_config_matches(self, window):
        return self.config._get_matches(self._display)

    def create_context(self, window, config, share_context=None):
        context = glXCreateNewContext(self._display, 
            config._fbconfig, GLX_RGBA_TYPE, share_context, True)
        if context == GLXBadContext:
            raise XlibException('Invalid context share')
        elif context == GLXBadFBConfig:
            raise XlibException('Invalid GL configuration')
        elif context < 0:
            raise XlibException('Could not create GL context') 

        window._glx_window = glXCreateWindow(self._display,
            config._fbconfig, window._window, None)
        return context

    def create_window(self, width, height):
        return XlibWindow(width, height, self._display)


class XlibWindow(BaseWindow):
    def __init__(self, width, height, display):
        super(XlibWindow, self).__init__(width, height)
        self._display = display

        # XXX the WM can probably tell us this
        self.x = 0
        self.y = 0

        black = xlib.XBlackPixel(self._display, 
            xlib.XDefaultScreen(self._display))
        self._window = xlib.XCreateSimpleWindow(self._display,
            xlib.XDefaultRootWindow(self._display), 
            0, 0, width, height, 0, black, black)

        # Listen for WM_DELETE_WINDOW
        wm_delete_window = xlib.XInternAtom(self._display,
            'WM_DELETE_WINDOW', False)
        wm_delete_window = c_ulong(wm_delete_window)
        xlib.XSetWMProtocols(self._display, self._window,
            byref(wm_delete_window), 1)

        # Map the window, listening for the window mapping event
        xlib.XSelectInput(self._display, self._window, StructureNotifyMask)
        xlib.XMapWindow(self._display, self._window)
        e = XEvent()
        while True:
            xlib.XNextEvent(self._display, e)
            if e.type == MapNotify:
                break

        # Now select all events (don't want PointerMotionHintMask)
        xlib.XSelectInput(self._display, self._window, 0x1ffff7f)

    def close(self):
        glXDestroyContext(self._display, self.context)
        glXDestroyWindow(self._display, self._glx_window)
        xlib.XDestroyWindow(self._display, self._window)

    def switch_to(self):
        glXMakeContextCurrent(self._display,
            self._glx_window, self._glx_window, self.context)

    def flip(self):
        glXSwapBuffers(self._display, self._glx_window)

    def dispatch_events(self):
        e = XEvent()

        # Check for the events specific to this window
        while xlib.XCheckWindowEvent(self._display, self._window,
                0x1ffffff, byref(e)):
            event_translator = self.__event_translators.get(e.type)
            if event_translator:
                event_translator(self, e)

        # Now check generic events for this display and manually filter
        # them to see whether they're for this window. sigh.
        # Store off the events we need to push back so we don't confuse
        # XCheckTypedEvent
        push_back = []
        while xlib.XCheckTypedEvent(self._display, ClientMessage, byref(e)):
            if e.xclient.window != self._window:
                push_back.append(e)
                e = XEvent()  # <ah> Let's not break the event we're storing.
            else:
                event_translator = self.__event_translators.get(e.type)
                if event_translator:
                    event_translator(self, e)
        for e in push_back:
            xlib.XPutBackEvent(self._display, byref(e))

    def _set_property(self, name, value, allow_utf8=True):
        atom = xlib.XInternAtom(self._display, name, True)
        if not atom:
            raise XlibException('Undefined atom "%s"' % name)
        if type(value) in (str, unicode):
            property = XTextProperty()
            if _have_utf8 and allow_utf8:
                buf = create_string_buffer(value.encode('utf8'))
                result = xlib.Xutf8TextListToTextProperty(self._display,
                    byref(pointer(buf)), 1, XUTF8StringStyle, byref(property))
                if result < 0:
                    raise XlibException('Could not create UTF8 text property')
            else:
                buf = create_string_buffer(value.encode('ascii', 'ignore'))
                result = xlib.XStringListToTextProperty(byref(pointer(buf)),
                    1, byref(property))
                if result < 0:
                    raise XlibException('Could not create text property')
            xlib.XSetTextProperty(self._display, 
                self._window, byref(property), atom)
            # XXX <rj> Xlib doesn't like us freeing this
            #xlib.XFree(property.value)

    def set_title(self, title):
        self._title = title
        self._set_property('WM_NAME', title, allow_utf8=False)
        self._set_property('WM_ICON_NAME', title, allow_utf8=False)
        self._set_property('_NET_WM_NAME', title)
        self._set_property('_NET_WM_ICON_NAME', title)

    def get_title(self):
        return self._title

    def __translate_key(window, event):
        if event.type == KeyRelease:
            # Look in the queue for a matching KeyPress with same timestamp,
            # indicating an auto-repeat rather than actual key event.
            auto_event = XEvent()
            result = xlib.XCheckTypedWindowEvent(window._display,
                window._window, KeyPress, byref(auto_event))
            if result and event.xkey.time == auto_event.xkey.time:
                buffer = create_string_buffer(16)
                count = xlib.XLookupString(byref(auto_event), 
                                           byref(buffer), 
                                           len(buffer), 
                                           c_void_p(),
                                           c_void_p())
                if count:
                    text = buffer.value[:count]
                else:
                    raise NotImplementedError, 'XLookupString had no idea'
                window.dispatch_event(EVENT_TEXT, text)
                return
            elif result:
                # Whoops, put the event back, it's for real.
                xlib.XPutBackEvent(window._display, byref(event))

        # pyglet.window.key keysymbols are identical to X11 keysymbols, no
        # need to map the keysymbol.
        text = None 
        if event.type == KeyPress:
            buffer = create_string_buffer(16)
            # TODO lookup UTF8
            count = xlib.XLookupString(byref(event), 
                                       byref(buffer), 
                                       len(buffer), 
                                       c_void_p(),
                                       c_void_p())
            if count:
                text = unicode(buffer.value[:count])
        symbol = xlib.XKeycodeToKeysym(window._display, event.xkey.keycode, 0)

        modifiers = _translate_modifiers(event.xkey.state)

        if event.type == KeyPress:
            window.dispatch_event(EVENT_KEYPRESS, symbol, modifiers)
            if (text and 
                (unicodedata.category(text) != 'Cc' or text == '\r')):
                window.dispatch_event(EVENT_TEXT, text)
        elif event.type == KeyRelease:
            window.dispatch_event(EVENT_KEYRELEASE, symbol, modifiers)

    def __translate_motion(window, event):
        x = event.xmotion.x
        y = event.xmotion.y
        dx = x - window.mouse.x
        dy = y - window.mouse.y
        window.mouse.x = x
        window.mouse.y = y
        window.dispatch_event(EVENT_MOUSEMOTION, x, y, dx, dy)

    def __translate_clientmessage(window, event):
        wm_delete_window = xlib.XInternAtom(event.xclient.display,
            'WM_DELETE_WINDOW', False)
        if event.xclient.data.l[0] == wm_delete_window:
            window.dispatch_event(EVENT_CLOSE)
        else:
            raise NotImplementedError

    def __translate_button(window, event):
        modifiers = _translate_modifiers(event.xbutton.state)
        if event.type == ButtonPress:
            window.mouse.buttons[event.xbutton.button] = True
            window.dispatch_event(EVENT_BUTTONPRESS, event.xbutton.button,
                event.xbutton.x, event.xbutton.y, modifiers)
        else:
            window.mouse.buttons[event.xbutton.button] = False
            window.dispatch_event(EVENT_BUTTONRELEASE, event.xbutton.button,
                event.xbutton.x, event.xbutton.y, modifiers)

    def __translate_expose(window, event):
        # Ignore all expose events except the last one. We could be told
        # about exposure rects - but I don't see the point since we're
        # working with OpenGL and we'll just redraw the whole scene.
        if event.xexpose.count > 0: return
        window.dispatch_event(EVENT_EXPOSE)

    def __translate_enter(window, event):
        # figure active mouse buttons
        # XXX ignore modifier state?
        state = event.xcrossing.state
        window.mouse.buttons[1] = state & Button1Mask
        window.mouse.buttons[2] = state & Button2Mask
        window.mouse.buttons[3] = state & Button3Mask
        window.mouse.buttons[4] = state & Button4Mask
        window.mouse.buttons[5] = state & Button5Mask

        # mouse position
        x = window.mouse.x = event.xcrossing.x
        y = window.mouse.y = event.xcrossing.y

        # XXX there may be more we could do here
        window.dispatch_event(EVENT_ENTER, x, y)

    def __translate_leave(window, event):
        # XXX do we care about mouse buttons?
        x = window.mouse.x = event.xcrossing.x
        y = window.mouse.y = event.xcrossing.y
        window.dispatch_event(EVENT_LEAVE, x, y)

    def __translate_configure(window, event):
        w, h = event.xconfigure.width, event.xconfigure.height
        x, y = event.xconfigure.x, event.xconfigure.y
        if window.width != w or window.height != h:
            window.dispatch_event(EVENT_RESIZE, w, h)
            window.width = w
            window.height = h
        if window.x != x or window.y != y:
            window.dispatch_event(EVENT_MOVE, x, y)
            window.x = x
            window.y = y

    __event_translators = {
        KeyPress: __translate_key,
        KeyRelease: __translate_key,
        MotionNotify: __translate_motion,
        ButtonPress: __translate_button,
        ButtonRelease: __translate_button,
        ClientMessage: __translate_clientmessage,
        Expose: __translate_expose,
        EnterNotify: __translate_enter,
        LeaveNotify: __translate_leave,
        ConfigureNotify: __translate_configure,
    }

def _translate_modifiers(state):
    modifiers = 0
    if state & ShiftMask:
        modifiers |= MOD_SHIFT  
    if state & ControlMask:
        modifiers |= MOD_CTRL
    if state & LockMask:
        modifiers |= MOD_CAPSLOCK
    if state & Mod1Mask:
        modifiers |= MOD_ALT
    if state & Mod2Mask:
        modifiers |= MOD_NUMLOCK
    if state & Mod4Mask:
        modifiers |= MOD_WINDOWS
    return modifiers

_attribute_ids = {
    'buffer_size': GLX_BUFFER_SIZE,
    'level': GLX_LEVEL,
    'doublebuffer': GLX_DOUBLEBUFFER,
    'stereo': GLX_STEREO,
    'aux_buffers': GLX_AUX_BUFFERS,
    'red_size': GLX_RED_SIZE,
    'green_size': GLX_GREEN_SIZE,
    'blue_size': GLX_BLUE_SIZE,
    'alpha_size': GLX_ALPHA_SIZE,
    'depth_size': GLX_DEPTH_SIZE,
    'stencil_size': GLX_STENCIL_SIZE,
    'accum_red_size': GLX_ACCUM_RED_SIZE,
    'accum_green_size': GLX_ACCUM_GREEN_SIZE,
    'accum_blue_size': GLX_ACCUM_BLUE_SIZE,
    'accum_alpha_size': GLX_ACCUM_ALPHA_SIZE,
    'sample_buffers': GLX_SAMPLE_BUFFERS,
    'samples': GLX_SAMPLES,
    'render_type': GLX_RENDER_TYPE,
    'config_caveat': GLX_CONFIG_CAVEAT,
    'transparent_type': GLX_TRANSPARENT_TYPE,
    'transparent_index_value': GLX_TRANSPARENT_INDEX_VALUE,
    'transparent_red_value': GLX_TRANSPARENT_RED_VALUE,
    'transparent_green_value': GLX_TRANSPARENT_GREEN_VALUE,
    'transparent_blue_value': GLX_TRANSPARENT_BLUE_VALUE,
    'transparent_alpha_value': GLX_TRANSPARENT_ALPHA_VALUE,
}

class XlibGLConfig(BaseGLConfig):
    def __init__(self, display=None, fbconfig=None):
        super(XlibGLConfig, self).__init__()
        self._display = display
        self._fbconfig = fbconfig
        if self._fbconfig:
            for name, attr in _attribute_ids.items():
                value = c_int()
                result = glXGetFBConfigAttrib(self._display, 
                    self._fbconfig, attr, byref(value))
                if result >= 0:
                    self._attributes[name] = value.value

    def _get_matches(self, display):
        attrs = []
        for name, value in self._attributes.items():
            attr = _attribute_ids.get(name, None)
            if not attr:
                raise XlibException('Unknown GLX attribute "%s"' % name)
            attrs.append(attr)
            attrs.append(int(value))
        if len(attrs):
            attrs.append(0)
            attrs.append(0)
            attrib_list = (c_int * len(attrs))(*attrs)
        else:
            attrib_list = None
        elements = c_int()
        screen = 0  # XXX what is this, anyway?
        configs = glXChooseFBConfig(display, 
            screen, attrib_list, byref(elements))
        if configs:
            result = []
            for i in range(elements.value):
                result.append(XlibGLConfig(display, configs[i]))
            xlib.XFree(configs)
            return result
        else:
            return []

