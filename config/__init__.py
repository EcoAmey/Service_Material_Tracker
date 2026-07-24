# Make PyMySQL act as the MySQLdb driver Django's mysql backend expects,
# since mysqlclient needs a C compiler that isn't set up on this machine.
import pymysql

pymysql.install_as_MySQLdb()
