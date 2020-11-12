# Docker Alpine Knowage Companion + S6 Overlay

## Auto configuration parameters 

Here we use the same configuration parameter names that knowage for easier configuration.

- SEARCH_USER_BEFORE_USER=uid=admin,dc=example,dc=com (The LDAP user the companion will use to search for users)
- SEARCH_USER_BEFORE_PSW=password (The LDAP admin password)
- SEARCH_USER_BEFORE_FILTER=(uid=%s) (The LDAP filter for users who will get an access to knowage)
- LDAP_BASE_DN=dc=example,dc=com (LDAP base dn for research)
- PROVIDER_URL=127.0.0.1 (LDAP URL)
- LDAP_PORT=389 (LDAP PORT)

- DB_TYPE=MARIADB (Database type, the companion also handle postgresql)
- DB_DB=knowage (Database name)
- DB_USER=knowage (Database username)
- DB_PASS=knowage (Database user password)
- DB_HOST=127.0.0.1 (Database URL)
- DB_PORT=3306 (Database port)

## Compose example :

    version: "3.1"
    services:
      knowage:
        image: knowagelabs/knowage-server-docker:7.2
        depends_on:
          - knowagedb
        ports:
          - "8080:8080"
        networks:
          - main
        environment:
          - DB_USER=knowage
          - DB_PASS=knowage
          - DB_DB=knowage
          - DB_HOST=knowagedb
          - DB_PORT=3306
          - HMAC_KEY=abc123
          - PASSWORD_ENCRYPTION_SECRET=def456
          - PUBLIC_ADDRESS=localhost
    
      knowagedb:
        image: mariadb:10.3
        environment:
          - MYSQL_USER=knowage
          - MYSQL_PASSWORD=knowage
          - MYSQL_DATABASE=knowage
          - MYSQL_ROOT_PASSWORD=temp
        networks:
          - main
        volumes:
          - "db:/var/lib/mysql"
        ports:
        - "3306:3306"
    
      cron:
        build: .
        environment:
          - SEARCH_USER_BEFORE_USER=uid=admin,dc=example,dc=com
          - SEARCH_USER_BEFORE_PSW=password
          - SEARCH_USER_BEFORE_FILTER=(uid=%s)
          - LDAP_BASE_DN=dc=example,dc=com
          - PROVIDER_URL=127.0.0.1
          - LDAP_PORT=389
    
          - DB_TYPE=MARIADB
          - DB_DB=knowage
          - DB_USER=knowage
          - DB_PASS=knowage
          - DB_HOST=127.0.0.1
          - DB_PORT=3306
    
    volumes:
      db:
    
    networks:
      main: