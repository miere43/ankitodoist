from aqt import mw, gui_hooks
from aqt.utils import qconnect
from aqt.qt import *
from datetime import date
from typing import List, MutableMapping
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from urllib.parse import urlencode
import urllib.parse
from datetime import date
import json
from uuid import uuid4
from aqt.utils import tooltip

def get_due_cards_search_query(ignore_decks: List[str]) -> str:
    args = ["is:due"]
    for deck in ignore_decks:
        args.append("-\"deck:%s\"" % deck)
    return " ".join(args)

def logic() -> None:
    config = mw.addonManager.getConfig(__name__)
    query = get_due_cards_search_query(config["ignore_decks"])
    print("query: %s" % query)
    due_cards = mw.col.find_cards(query)
    print("due_cards: %d" % len(due_cards))
    if len(due_cards) != 0:
        print("ignore task completion: have %d due tasks" % len(due_cards))
        return
    todoist = TodoistClient(config["todoist_token"])
    task = todoist.get_active_task(config["task_id"])
    if task.due_date != date.today():
        print("ignore task completion: %s != %s" % (task.due_date, date.today()))
        return
    todoist.complete_recurring_task(task)
    tooltip('Marked Todoist task as completed!')

action = QAction("Todoist sync", mw)
qconnect(action.triggered, logic)
mw.form.menuTools.addAction(action)

def sync_did_finish() -> None:
    logic()

gui_hooks.sync_did_finish.append(sync_did_finish)

class TodoistActiveTask:
    id: str
    due_date: date
    is_recurring: bool

class TodoistClient:
    api_token: str

    def __init__(self, api_token: str):
        self.api_token = api_token

    def get_active_task(self, task_id: str) -> TodoistActiveTask:
        task = TodoistActiveTask()
        task.id = task_id
        request = Request("https://api.todoist.com/rest/v2/tasks/%s" % task_id, headers=self._headers())
        with urlopen(request) as response:
            body = json.load(response)
            task.is_recurring = body["due"]["is_recurring"]
            task.due_date = date.fromisoformat(body["due"]["date"])
        return task

    def complete_recurring_task(self, task: TodoistActiveTask) -> None:
        if not task.is_recurring:
            raise Exception("Task must be recurring")
        data = urlencode({
            "commands": json.dumps([
                {
                    "type": "item_update_date_complete",
                    "uuid": str(uuid4()),
                    "args": {
                        "id": task.id,
                    },
                },
            ]),
        }, quote_via=urllib.parse.quote)
        print(data)
        request = Request("https://api.todoist.com/sync/v9/sync", headers=self._headers(), method="POST", data=bytes(data, encoding="utf-8"))
        try:
            with urlopen(request) as r:
                pass
        except HTTPError as e:
            print(e.read())
            raise

    def _headers(self) -> MutableMapping[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer %s" % self.api_token,
        }
