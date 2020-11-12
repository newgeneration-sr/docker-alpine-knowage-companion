#!/usr/bin/with-contenv /usr/bin/python3

from ldap3 import Server, Connection, ALL, NTLM, SUBTREE, NONE
from datetime import datetime
import os
import json
import psycopg2

try:
    import MySQLdb as mysql
except:
    mysql = None
    print("""
     **** Local mysql driver is not found, consider installing it ****
            sudo apt install python3-mysqldb
    """)


class Retriever:

    def __init__(self):
        """
            Paramètres de LDAP et de la base de données de Knowage
        """

        self.vars = {
            "SEARCH_USER_BEFORE_USER": os.environ.get("SEARCH_USER_BEFORE_USER", "uid=admin,dc=example,dc=com"),
            "SEARCH_USER_BEFORE_PSW": os.environ.get("SEARCH_USER_BEFORE_PSW", ""),
            "SEARCH_USER_BEFORE_FILTER": os.environ.get("SEARCH_USER_BEFORE_FILTER", "(uid=%s)"),
            "LDAP_BASE_DN": os.environ.get("LDAP_BASE_DN", "dc=example,dc=com"),
            "PROVIDER_URL": os.environ.get("PROVIDER_URL", "127.0.0.1"),
            "LDAP_PORT": os.environ.get("LDAP_PORT", "389"),

            "DB_TYPE": os.environ.get("DB_TYPE", "MARIADB"),
            "DB_DB": os.environ.get("DB_DB", "knowage"),
            "DB_USER": os.environ.get("DB_USER", "knowage"),
            "DB_PASS": os.environ.get("DB_PASS", "knowage"),
            "DB_HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "DB_PORT": os.environ.get("DB_PORT", "3306"),
        }

        """
            Requêtes SQL et Classe (MySQL ou Postgres)
        """
        self.db = {
            "CLASS": mysql if self.vars["DB_TYPE"].upper() == "MYSQL" or self.vars[
                "DB_TYPE"].upper() == "MARIADB" else psycopg2,

            "GET_MAX_ID_REQUEST": "SELECT next_val FROM hibernate_sequences WHERE sequence_name='SBI_USER';",
            "GET_USERS": "SELECT DISTINCT USER_ID FROM SBI_USER;",

            "UPDATE_SEQUENCE_REQUEST": "UPDATE hibernate_sequences SET next_val=%(new_val)s WHERE next_val=%(old_val)s and sequence_name='SBI_USER';",
            "INSERT_REQUEST": "INSERT INTO SBI_USER (USER_ID, FULL_NAME, USER_IN, ORGANIZATION, ID) VALUES (%(uid)s, %(uid)s, 'biadmin', 'DEFAULT_TENANT', %(id)s);",
            "DELETE_REQUEST": "DELETE FROM SBI_USER WHERE USER_ID = %(uid)s;",

        }

        """
            Utilisateurs qui ne seront jamais supprimés de knowage et qui ont un mot de passe défini
        """
        self.admin_knowage_users = os.environ.get("ADMIN_KNOWAGE_USERS", "'biadmin', 'bidemo', 'bidev', 'bitest', 'biuser'").split(",")

    def __execute_query__(self, query, values={}, fetch_all=False, fetch_one=False):
        ret = None
        cursor = None
        connection = None

        try:
            self.log(f"Executing : {query % values}")

            connection = self.db["CLASS"].connect(user=self.vars["DB_USER"],
                                                  password=self.vars["DB_PASS"],
                                                  host=self.vars["DB_HOST"],
                                                  port=int(self.vars["DB_PORT"]),
                                                  database=self.vars["DB_DB"])

            cursor = connection.cursor()
            cursor.execute(query, values)

            if fetch_all:
                ret = cursor.fetchall()

            if fetch_one:
                ret = cursor.fetchone()

            connection.commit()

        except (Exception, psycopg2.Error, mysql.Error) as error:
            self.log(f"Error while fetching data from {self.vars['DB_TYPE']}, the error is : ")
            self.log(str(error))

        finally:
            # closing database connection.
            if (connection):
                cursor.close()
                connection.close()

        if fetch_one or fetch_all:
            return ret

    def __get_users_from_ldap__(self):
        ldap_users = []

        try:
            server = Server(self.vars["PROVIDER_URL"], port=int(self.vars["LDAP_PORT"]), get_info=ALL)

            conn = Connection(server=server,
                              user=self.vars["SEARCH_USER_BEFORE_USER"],
                              password=self.vars["SEARCH_USER_BEFORE_PSW"],
                              auto_bind=True,
                              version=3,
                              auto_referrals=True)

            conn.search(search_base=self.vars["LDAP_BASE_DN"],
                        search_filter=self.vars["SEARCH_USER_BEFORE_FILTER"] % "*",
                        search_scope=SUBTREE,
                        attributes="uid")

            result = conn.entries
            ldap_users = [json.loads(elt.entry_to_json())["attributes"]["uid"][0] for elt in result]

            conn.unbind()
        except Exception as error:
            self.log("""
                An error occured while retrieving ldap users
            """)
            self.log(str(error))

        return ldap_users

    def __add_user_to_knowage__(self, uid):
        next_id = self.__execute_query__(query=self.db["GET_MAX_ID_REQUEST"], fetch_one=True)[0]

        self.__execute_query__(query=self.db["UPDATE_SEQUENCE_REQUEST"],
                               values={"new_val": next_id + 1, "old_val": next_id})

        self.__execute_query__(query=self.db["INSERT_REQUEST"], values={"uid": uid, "id": next_id})

    def __get_users_from_knowage__(self):
        users = self.__execute_query__(query=self.db["GET_USERS"], fetch_all=True)

        if users is not None:
            users = [user[0] for user in users]
        else:
            users = []

        return users

    def __delete_user_in_knowage__(self, knowage_user):
        self.__execute_query__(query=self.db["DELETE_REQUEST"], values={"uid": knowage_user})

    def print_configuration(self):
        self.log(" *** Configuration *** ")
        indent = 0
        for key, value in self.vars.items():
            self.log('\t' * indent + str(key) + " -> " + str(value))

        self.log(" *** End Configuration *** ")

    def log(self, log):
        date = datetime.now()

        log_prefix = date.strftime("%Y-%m-%d %H:%M:%S")
        logfile_suffix = date.strftime("%Y-%m-%d")

        with open(f"/var/log/retriever-{logfile_suffix}.log", "a") as file:
            file.write(log_prefix + " " + log + "\n")

    def synchronize_users(self):
        self.log("Start synchronizing ...")
        ldap_users = self.__get_users_from_ldap__()
        ldap_users_not_in_knowage = []

        knowage_users = self.__get_users_from_knowage__()
        knowage_users_not_in_ldap = []

        if len(ldap_users) == 0:
            self.log("No user was found in LDAP or connexion was unsuccessful. Please, check your configuration :")
            self.print_configuration()
        elif len(knowage_users) == 0:
            self.log("No user was found in Knowage or connexion was unsuccessful. Please, check your configuration :")
            self.print_configuration()
        else:
            # Ajout des utilisateurs présent dans ldap non présent dans knowage
            for ldap_user in ldap_users:
                if ldap_user not in knowage_users:
                    ldap_users_not_in_knowage.append(ldap_user)
                    self.__add_user_to_knowage__(ldap_user)

            # Suppression des utilisateurs qui ne sont plus dans ldap
            for knowage_user in knowage_users:
                if knowage_user not in ldap_users and knowage_user not in self.admin_knowage_users:
                    knowage_users_not_in_ldap.append(knowage_user)
                    self.__delete_user_in_knowage__(knowage_user)

            if len(ldap_users_not_in_knowage) != 0:
                self.log("We have added ldap users to knowage the following users : " + str(ldap_users_not_in_knowage))

            if len(knowage_users_not_in_ldap) != 0:
                self.log("We have deleted non admin knowage users not in ldap : " + str(knowage_users_not_in_ldap))

            self.log("Synchronized !")


if __name__ == "__main__":
    retriver = Retriever()
    retriver.synchronize_users()
    exit(0)
