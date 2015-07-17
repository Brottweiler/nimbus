#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Slack bot for Overcast Network """

import sys
import time
import logging
import logging.config
import json
import signal
import yaml
import os
import inspect
from slackclient import SlackClient
from plugin import Plugin, CommandPlugin

# Log to file and SDOUT
logging.config.fileConfig('logging.conf')
log = logging.getLogger(__name__)
logging.captureWarnings(True)


class Nimbus(object):
    """
    Main bot class
    """

    def get_config(self, filename):
        """ Gets the bot config file """
        try:
            return yaml.safe_load(file(filename))
        except IOError as e:
            raise SystemExit("Couldn't open configuration file: %s" % e)

    def process_event(self, event):
        """
        Processes an event and invokes plugins
        """
        # Copy the event in order to prevent changes from propagating to other plugins
        # Some plugins (like CommandPlugins) decide to edit the event in-place
        event_copy = dict(event)

        for plugin in filter(lambda p: p.event_type == event_copy['type'], self.plugins):
            # JSON Response for all API calls
            response = dict(username=self.username, icon_emoji=self.icon_emoji)
            if 'channel' in event_copy:
                response.update({'channel': event['channel']})

            plugin.on_event(self, event_copy, response)

    def run(self):
        """
        Main loop
        """
        log.info("Starting bot loop...")
        while True:
            events = self.sc.rtm_read()
            for event in events:
                # Don't listen to the bot's own messages or other bot messages
                if event.get('subtype', '') != 'bot_message':
                    self.process_event(event)

            time.sleep(self.polling_interval)

    def register_plugin(self, plugin):
        """
        Registers the specified plugin with the bot 
        """
        if not type(plugin) is type or not issubclass(plugin, Plugin):
            log.warning('Module %s not subclass of Plugin! Skipping...' % plugin.__name__)
            return

        # Instantiate class and add to plugins list
        self.plugins.append(plugin())
        log.info('Successfully registered plugin \'%s\'' % plugin.__name__)

    def load_plugins(self):
        """
        Loads all plugins from the /plugins/ directory
        """
        log.info('Registering plugins...')
        plugin_directory = 'plugins'  # TODO Config setting?
        # Loop through files in plugin directory
        for f in os.listdir(plugin_directory):
            module_name, extension = os.path.splitext(f)
            if extension == ".py":
                module_path = '%s.%s' % (plugin_directory, module_name)
                imported = __import__(module_path, fromlist=[module_name])

                # Find all the Plugin classes in the module
                # This means you could have mltiple plugins per module
                class_filter = lambda c: inspect.isclass(c) and c.__module__ == module_path and issubclass(c, Plugin)
                classes = inspect.getmembers(imported, class_filter)

                # Register all found plugin classes
                for name, klass in classes:
                    self.register_plugin(klass)

    def get_command(self, trigger):
        """
        Returns a command plugin instance contains the specified trigger
        (if there is one)
        """
        # TODO This might get a bit slow when we have a lot of plugins
        # Consider another data structure for storing loaded plugins

        for plugin in filter(lambda p: isinstance(p, CommandPlugin), self.plugins):
            for trig in plugin.triggers:
                if trigger == trig:
                    return plugin

    def __init__(self, config_name):
        """
        Bot constructor
        """
        log.info("Initializing Nimbus instance...")
        config = self.get_config(config_name)

        self.username = config.get('username', 'nimbus')
        self.icon_emoji = ':' + config.get('icon_emoji', 'cloud') + ':'
        self.polling_interval = config.get('polling_interval', 1)
        self.command_prefix = config.get('command_prefix', '!')
        self.plugins = []

        self.token = config.get('token')
        if not self.token:
            raise SystemExit('Need an authorization token.')

        self.sc = SlackClient(self.token)
        if not self.sc.rtm_connect():
            raise SystemExit("Can't connect to Slack.")
        log.info('Successfully authenticated with Slack!')

        self.load_plugins()


def sigint_handler(signum, frame):
    """
    Handle ctr-c gracefully
    """
    result = raw_input("\nReally quit? (y/n)")
    if result.startswith('y'):
        log.info('Shutting down...')
        sys.exit()


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        config_filename = sys.argv[1]
        signal.signal(signal.SIGINT, sigint_handler)
        Nimbus(config_filename).run()
    else:
        raise SystemExit('Please include the name of a configuration file')
