FROM dotriver/alpine-s6

RUN apk update --no-cache \
    && apk add python3 py3-mysqlclient

RUN apk update --no-cache \
    && apk add py3-pip gcc python3-dev musl-dev postgresql-dev \
    && pip3 install psycopg2-binary ldap3
    && apk del py3-pip gcc python3-dev musl-dev postgresql-dev

ADD ./conf /