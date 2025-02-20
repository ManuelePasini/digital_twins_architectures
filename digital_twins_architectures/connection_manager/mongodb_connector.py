from pymongo import MongoClient
import sys, os

utils_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.path.join("..", "..", ".."))
)
sys.path.insert(0, utils_dir)
from utils import utils


class MongoDBConnector:

    def __init__(self, mongo_ip, mongo_port):
        self.__client = MongoClient(f"mongodb://{mongo_ip}:{mongo_port}/")
        self.__current_db = None
        self.__current_collection = None
        self.__logger = utils.setup_logger("MongoDB_Connector")

    ## Utility functions

    def __check_collection(self, collection_name):
        collection_name = collection_name or self.__current_collection
        if collection_name is not None:
            return collection_name
        else:
            raise Exception(
                "No database name has been set. Set it with either client.set_database(db_name) or pass it as function parameter"
            )

    def __check_db(self, db_name):
        db_name = db_name or self.__current_db
        if db_name is not None:
            return db_name
        else:
            raise Exception(
                "No database name has been set. Set it with either client.set_database(db_name) or pass it as function parameter"
            )

    ###

    def set_database(self, db_name):
        if db_name is not None:
            self.__current_db = db_name
        else:
            raise Exception(f"Cant set {db_name} as default database")

    def set_collection(self, collection_name):
        if collection_name is not None:
            self.__current_collection = collection_name
        else:
            raise Exception(f"Cant set {collection_name} as default collection")

    def get_database(self, db_name=None):
        if self.__check_db(db_name):
            return self.__client[db_name or self.__current_db]
        else:
            raise Exception("Pleace select a valid database name")

    def list_collections(self, db_name=None):
        if self.__check_db(db_name):
            return self.__client[db_name or self.__current_db].list_collection_names()

    def get_collection(self, db_name=None, collection_name=None):
        if self.__check_collection(collection_name):
            return self.get_database(db_name)[
                collection_name or self.__current_collection
            ]
        else:
            raise Exception("Pleace select a valid collection name")

    def insert_into_collection(self, data, db_name=None, collection_name=None):
        if isinstance(data, list) > 1:
            return self.get_collection(db_name, collection_name).insert_many(data)
        else:
            return self.get_collection(db_name, collection_name).insert_one(data)

    def find(self, db_name=None, collection_name=None, query=None, limit=sys.maxsize):
        result = (
            self.get_collection(db_name, collection_name).find(query or {}).limit(limit)
        )
        return list(result)

    def count_documents(self, db_name=None, collection_name=None, query=None):
        return self.get_collection(db_name, collection_name).count_documents(
            query or {}
        )
