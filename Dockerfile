# nutrition-irrigation-model-1.2.0

FROM python:3.9-slim

RUN mkdir /src
# Copy REQUIREMENT_FILE in src folder
COPY requirements.txt  /src/

RUN apt-get update \
&& apt-get install gcc -y \
&& apt-get clean

RUN pip install --upgrade pip
RUN pip install -r src/requirements.txt
RUN pip install flake8 black

# Set PYTHONPATH
ENV PYTHONPATH="/src/:$PATH"
ENV TZ="Europe/Rome"
