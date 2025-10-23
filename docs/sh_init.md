Connecting to your local browser
Connect to your existing local Chrome/Chromium browser instead of launching a new one. This lets you automate your normal browser with all your existing tabs, extensions and settings.

TypeScript

Python

Copy

Ask AI
from stagehand import Stagehand

stagehand = Stagehand(
    env="LOCAL",
    local_browser_launch_options={
      cdp_url="http://localhost:9222"
    }
)

await stagehand.init()