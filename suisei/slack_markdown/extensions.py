from marko import MarkoExtension
from marko.ext.gfm import GFM

SLACK_EXTENSION = MarkoExtension(elements=GFM.elements)
