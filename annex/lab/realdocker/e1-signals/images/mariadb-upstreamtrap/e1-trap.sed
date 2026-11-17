/^trap '\/usr\/bin\/mysqladmin --defaults-extra-file=\/etc\/mysql\/debian.cnf refresh & wait' 1 # HUP$/c\
trap '' 1 2 3 15  # e1 edit: the signal handling of upstream MariaDB scripts/mysqld_safe.sh:41
/^trap '\/usr\/bin\/mysqladmin --defaults-extra-file=\/etc\/mysql\/debian.cnf shutdown' 2 3 15 # INT QUIT and TERM$/d
