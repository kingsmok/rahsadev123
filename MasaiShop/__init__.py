"""Project package initialization.

PyMySQL provides a portable MySQL driver on shared hosts where compiling the
native ``mysqlclient`` extension is usually unavailable.
"""

try:
    import pymysql
except ImportError:
    # PostgreSQL/SQLite deployments do not need the optional MySQL driver.
    pass
else:
    pymysql.install_as_MySQLdb()
