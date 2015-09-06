from plugin import Plugin
import re


class React(Plugin):
    """
    Adds Slack emoji reactions to messages based on certain keywords
    """

    def on_event(self, event, response):
        text = event['text']
        response.update(timestamp=event['ts'])

        # Add a cloud emoji if anyone mentions Overcast Network
        if re.search(r'(overcast|ocn)', text, re.IGNORECASE):
            response.update(name='cloud')

        # Add more reactions here!

        if re.search(r'(hause|hausemaster|hause master)', text, re.IGNORECASE):
            response.update(name='hause')

        if re.search(r'(popbob|poopboob)', text, re.IGNORECASE):
            response.update(name='popbob')

        if re.search(r'(2b2t)', text, re.IGNORECASE):
            response.update(name='poop')

        # Post reaction if we have an emoji set
        if response.get('name'):
            self.bot.sc.api_call('reactions.add', **response)
