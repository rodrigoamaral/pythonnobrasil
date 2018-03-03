from datetime import datetime

import attr
import yaml
from googleapiclient import discovery
from google.oauth2.service_account import Credentials
from ics import Calendar as ICSCalendar, Event as ICSEvent

import config

DATE_FORMAT = '%Y-%m-%d'


def _date_converter(value):
    if not isinstance(value, str):
        return value

    return datetime.strptime(value, DATE_FORMAT).date()


@attr.s
class Event:
    name = attr.ib()
    start = attr.ib(converter=_date_converter)
    end = attr.ib(converter=_date_converter)
    location = attr.ib()
    url = attr.ib()

    def __sub__(self, other):
        if not isinstance(other, Event):
            raise Exception()

        fields = [a.name for a in self.__attrs_attrs__]

        different_fields = []
        for field in fields:
            if getattr(self, field) != getattr(other, field):
                different_fields.append(field)

        return different_fields


class Calendar:
    def __getitem__(self, key):
        for event in self.events:
            if event.name == key:
                return event

        raise KeyError(key)

    def get(self, key, value=None):
        try:
            return self[key]
        except KeyError:
            return value



class YamlCalendar(Calendar):
    def __init__(self, path):
        self.events = []
        self.fetch(path)

    def fetch(self, path):
        with open(path) as events_file:
            events = yaml.load(events_file.read())

        for event_data in events:
            event = Event(**event_data)
            self.events.append(event)


class GoogleCalendar(Calendar):
    GOOGLE_API_SCOPES = ['https://www.googleapis.com/auth/calendar']

    def __init__(self):
        self.events = []
        self.fetch()

    @property
    def credentials(self):
        return Credentials.from_service_account_file(
            config.GOOGLE_API_AUTHORIZED_USER_FILE,
            scopes=self.GOOGLE_API_SCOPES)

    @property
    def google_client(self):
        return discovery.build('calendar', 'v3', credentials=self.credentials)

    def get_google_calendar_events(self):
        client = self.google_client.events()
        events = client.list(calendarId=config.GOOGLE_API_CALENDAR_ID).execute()
        return events['items']

    def fetch(self):
        events = self.get_google_calendar_events()
        for event_data in events:
            if event_data['status'] != 'confirmed':
                continue

            event = Event(
                name=event_data['summary'],
                start=event_data.get('start').get('date'),
                end=event_data.get('end').get('date'),
                location=event_data.get('location'),
                url=event_data.get('description'),
            )

            self.events.append(event)

    def _create_payload(self, event):
        return {
            'summary': event.name,
            'location': event.location,
            'description': event.url,
            'start': {
                'date': event.start.strftime(DATE_FORMAT),
            },
            'end': {
                'date': event.end.strftime(DATE_FORMAT),
            },
        }

    def create_event(self, event):
        client = self.google_client.events()

        payload = self._create_payload(event)
        event = client.insert(calendarId=config.GOOGLE_API_CALENDAR_ID,
                              body=payload).execute()
        # TODO: log request
