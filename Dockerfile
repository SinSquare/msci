FROM python:3.13
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./msci /code/msci

ADD startup.sh /
RUN chmod +x /startup.sh

ENTRYPOINT ["/startup.sh"]
