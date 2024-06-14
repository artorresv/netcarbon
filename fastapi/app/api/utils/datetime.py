from datetime import date, datetime


def datetime_from_string(date_string: str) -> datetime:
    _datetime = datetime.combine(datetime.strptime(date_string, '%Y-%m-%d').date(),
                                 datetime.now().astimezone().timetz())

    return _datetime


def date_from_string(date_string: str) -> date:
    _date = datetime.strptime(date_string, '%Y-%m-%d').date()

    return _date
