FROM neo4j

RUN apt-get update && apt-get install -y wget nano python3 python3-pip  && apt-get clean

RUN mkdir -p /neo4j
COPY . /neo4j/

RUN chmod -R 777 /neo4j

WORKDIR /neo4j

RUN pip3 install -r /neo4j/requirements.txt
EXPOSE 7474 7687 7473