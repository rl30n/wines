Using Docker Compose is a much more convenient way of running the solution in a container. This method is often used in local development environments to try out the product before a full production deployment.

This example runs Enterprise Search with Elasticsearch and Kibana in Docker Compose.

Create the following configuration files in a new, empty directory:

Create a .env file to set environment variables which are used to run the docker-compose.yml configuration file. Include these environment variables:

STACK_VERSION=8.17.4
ELASTIC_PASSWORD=changeme
KIBANA_PASSWORD=changeme
ES_PORT=9200
CLUSTER_NAME=es-cluster
LICENSE=basic
MEM_LIMIT=1073741824
KIBANA_PORT=5601
ENTERPRISE_SEARCH_PORT=3002
ENCRYPTION_KEYS=secret
Ensure that you specify a strong password for the elastic and kibana_system users with the ELASTIC_PASSWORD and KIBANA_PASSWORD variables. These variables are referenced by the docker-compose.yml file.

Create a docker-compose.yml file:

version: "2.2"

services:
  setup:
    image: docker.elastic.co/elasticsearch/elasticsearch:${STACK_VERSION}
    volumes:
      - certs:/usr/share/elasticsearch/config/certs
    user: "0"
    command: >
      bash -c '
        if [ x${ELASTIC_PASSWORD} == x ]; then
          echo "Set the ELASTIC_PASSWORD environment variable in the .env file";
          exit 1;
        elif [ x${KIBANA_PASSWORD} == x ]; then
          echo "Set the KIBANA_PASSWORD environment variable in the .env file";
          exit 1;
        fi;
        if [ ! -f certs/ca.zip ]; then
          echo "Creating CA";
          bin/elasticsearch-certutil ca --silent --pem -out config/certs/ca.zip;
          unzip config/certs/ca.zip -d config/certs;
        fi;
        if [ ! -f certs/certs.zip ]; then
          echo "Creating certs";
          echo -ne \
          "instances:\n"\
          "  - name: es01\n"\
          "    dns:\n"\
          "      - es01\n"\
          "      - localhost\n"\
          "    ip:\n"\
          "      - 127.0.0.1\n"\
          > config/certs/instances.yml;
          bin/elasticsearch-certutil cert --silent --pem -out config/certs/certs.zip --in config/certs/instances.yml --ca-cert config/certs/ca/ca.crt --ca-key config/certs/ca/ca.key;
          unzip config/certs/certs.zip -d config/certs;
        fi;
        echo "Setting file permissions"
        chown -R root:root config/certs;
        find . -type d -exec chmod 750 \{\} \;;
        find . -type f -exec chmod 640 \{\} \;;
        echo "Waiting for Elasticsearch availability";
        until curl -s --cacert config/certs/ca/ca.crt https://es01:9200 | grep -q "missing authentication credentials"; do sleep 30; done;
        echo "Setting kibana_system password";
        until curl -s -X POST --cacert config/certs/ca/ca.crt -u elastic:${ELASTIC_PASSWORD} -H "Content-Type: application/json" https://es01:9200/_security/user/kibana_system/_password -d "{\"password\":\"${KIBANA_PASSWORD}\"}" | grep -q "^{}"; do sleep 10; done;
        echo "All done!";
      '
    healthcheck:
      test: ["CMD-SHELL", "[ -f config/certs/es01/es01.crt ]"]
      interval: 1s
      timeout: 5s
      retries: 120

  es01:
    depends_on:
      setup:
        condition: service_healthy
    image: docker.elastic.co/elasticsearch/elasticsearch:${STACK_VERSION}
    volumes:
      - certs:/usr/share/elasticsearch/config/certs
      - esdata01:/usr/share/elasticsearch/data
    ports:
      - ${ES_PORT}:9200
    environment:
      - node.name=es01
      - cluster.name=${CLUSTER_NAME}
      - cluster.initial_master_nodes=es01
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - bootstrap.memory_lock=true
      - xpack.security.enabled=true
      - xpack.security.http.ssl.enabled=true
      - xpack.security.http.ssl.key=certs/es01/es01.key
      - xpack.security.http.ssl.certificate=certs/es01/es01.crt
      - xpack.security.http.ssl.certificate_authorities=certs/ca/ca.crt
      - xpack.security.http.ssl.verification_mode=certificate
      - xpack.security.transport.ssl.enabled=true
      - xpack.security.transport.ssl.key=certs/es01/es01.key
      - xpack.security.transport.ssl.certificate=certs/es01/es01.crt
      - xpack.security.transport.ssl.certificate_authorities=certs/ca/ca.crt
      - xpack.security.transport.ssl.verification_mode=certificate
      - xpack.license.self_generated.type=${LICENSE}
    mem_limit: ${MEM_LIMIT}
    ulimits:
      memlock:
        soft: -1
        hard: -1
    healthcheck:
      test:
        [
            "CMD-SHELL",
            "curl -s --cacert config/certs/ca/ca.crt https://localhost:9200 | grep -q 'missing authentication credentials'",
        ]
      interval: 10s
      timeout: 10s
      retries: 120

  kibana:
    depends_on:
      es01:
        condition: service_healthy
    image: docker.elastic.co/kibana/kibana:${STACK_VERSION}
    volumes:
      - certs:/usr/share/kibana/config/certs
      - kibanadata:/usr/share/kibana/data
    ports:
      - ${KIBANA_PORT}:5601
    environment:
      - SERVERNAME=kibana
      - ELASTICSEARCH_HOSTS=https://es01:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD}
      - ELASTICSEARCH_SSL_CERTIFICATEAUTHORITIES=config/certs/ca/ca.crt
      - ENTERPRISESEARCH_HOST=http://enterprisesearch:${ENTERPRISE_SEARCH_PORT}
    mem_limit: ${MEM_LIMIT}
    healthcheck:
      test:
        [
            "CMD-SHELL",
            "curl -s -I http://localhost:5601 | grep -q 'HTTP/1.1 302 Found'",
        ]
      interval: 10s
      timeout: 10s
      retries: 120

  enterprisesearch:
    depends_on:
      es01:
        condition: service_healthy
      kibana:
        condition: service_healthy
    image: docker.elastic.co/enterprise-search/enterprise-search:${STACK_VERSION}
    volumes:
      - certs:/usr/share/enterprise-search/config/certs
      - enterprisesearchdata:/usr/share/enterprise-search/config
    ports:
      - ${ENTERPRISE_SEARCH_PORT}:3002
    environment:
      - SERVERNAME=enterprisesearch
      - secret_management.encryption_keys=[${ENCRYPTION_KEYS}]
      - allow_es_settings_modification=true
      - elasticsearch.host=https://es01:9200
      - elasticsearch.username=elastic
      - elasticsearch.password=${ELASTIC_PASSWORD}
      - elasticsearch.ssl.enabled=true
      - elasticsearch.ssl.certificate_authority=/usr/share/enterprise-search/config/certs/ca/ca.crt
      - kibana.external_url=http://kibana:5601
    mem_limit: ${MEM_LIMIT}
    healthcheck:
      test:
        [
            "CMD-SHELL",
            "curl -s -I http://localhost:3002 | grep -q 'HTTP/1.1 302 Found'",
        ]
      interval: 10s
      timeout: 10s
      retries: 120

volumes:
  certs:
    driver: local
  enterprisesearchdata:
    driver: local
  esdata01:
    driver: local
  kibanadata:
    driver: local
This sample Docker Compose file brings up a single-node Elasticsearch cluster, then starts an Enterprise Search instance on it and configures a Kibana instance as the main way of interacting with the solution.

All components running in Docker compose are attached to a dedicated Docker network called elastic and are exposed via a set of local ports accessible only from the local machine. If you want to open up the service to other computers on your network, you will need to change port mappings for the services you want to share (e.g. change 127.0.0.1:5601:5601 to 5601:5601 for Kibana).

The --volume argument mounts a volume within the container. Elasticsearch will write a certificate file to this volume on startup. The Enterprise Search container will mount the same volume in order to read the certificate file.

The data in the Docker volumes is preserved and loaded when you restart the cluster with docker-compose up. To restart Elasticsearch later, you must first delete the volume so Elasticsearch can start with a fresh configuration:

docker volume rm es-config
Make sure Docker Engine is allotted at least 4GiB of memory. In Docker Desktop, configure resource usage using the Advanced tab in Preferences (macOS) or Settings (Windows).

Docker Compose is not pre-installed with Docker on Linux. See docs.docker.com for installation instructions: Install Compose on Linux

Run docker-compose up to bring up the cluster:

docker-compose up --remove-orphans
If the solution starts without errors, your deployment is ready to use:

Access Kibana at http://localhost:5601. Log in with user elastic. The password is the value you provided for ELASTIC_PASSWORD in your .env file.

Access Elasticsearch at http://localhost:9200.

Alternatively, if the solution does not start successfully, check the container logs for more information.

Try: docker logs <container_id>, where container_id is the ID of the unhealthy container (for example f6de943335cf).

If the container fails to start with a message about vm.max_map_count, refer to the following Elasticsearch documentation for platform-specific solutions: Using the Docker images in production.

To stop the cluster, run docker-compose down or press Ctrl+C in your terminal.

To delete the data volumes when you bring down the cluster, specify the -v option: docker-compose down -v.

