# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
from traceback import print_exc

from Plugins.Plugin import PluginDescriptor


shutdown = None


def main(session, **kwargs):
    global shutdown
    try:
        from . import interface
    except ImportError as error:
        print_exc()
        from Screens.MessageBox import MessageBox
        session.open(MessageBox, "E2PVR could not load: %s" % error, MessageBox.TYPE_ERROR)
        return
    shutdown = interface.shutdown
    interface.main(session, **kwargs)


def autostart(reason, **kwargs):
    if reason == 1 and shutdown is not None:
        shutdown()


def Plugins(**kwargs):
    return [PluginDescriptor(name="E2PVR", description="PVR subtitles", icon="plugin.png",
                             where=[PluginDescriptor.WHERE_PLUGINMENU, PluginDescriptor.WHERE_EXTENSIONSMENU],
                             fnc=main),
            PluginDescriptor(where=PluginDescriptor.WHERE_AUTOSTART, fnc=autostart)]
