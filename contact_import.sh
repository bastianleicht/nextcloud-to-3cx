_dbtable=$(sed -n 's/DBName = \(.*\)/\1/p' /var/lib/3cxpbx/Bin/3CXPhoneSystem.ini)
_dbport=$(sed -n '0,/DBPort = \(.*\)/s//\1/p' /var/lib/3cxpbx/Bin/3CXPhoneSystem.ini)
_dbuser=$(sed -n 's/MasterDBUser = \(.*\)/\1/p' /var/lib/3cxpbx/Bin/3CXPhoneSystem.ini)
_dbpassword=$(sed -n 's/MasterDBPassword = \(.*\)/\1/p' /var/lib/3cxpbx/Bin/3CXPhoneSystem.ini)
echo "127.0.0.1:$_dbport:$_dbtable:$_dbuser:$_dbpassword" > ~/.pgpass
chmod 600 ~/.pgpass
psql -d $_dbtable -h 127.0.0.1 -p $_dbport -U $_dbuser -c "DELETE FROM phonebook WHERE fkidtenant = 1";
psql -d $_dbtable -h 127.0.0.1 -p $_dbport -U $_dbuser -c "COPY phonebook(idphonebook, firstname, lastname, phonenumber, fkidtenant, fkiddn, company, tag, pv_an5, pv_an0, pv_an1, pv_an2, pv_an3, pv_an4, pv_an6, pv_an7, pv_an8, pv_an9) FROM '/home/scripts/3cx_contacts.csv' DELIMITER ',' CSV HEADER";
/etc/init.d/postgresql restart