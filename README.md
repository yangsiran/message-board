# setup:

In your Mysql database:

    create table users (
      id_ char(3),
      pass char(40),
      username varchar(20),
      first_name varchar(15),
      last_name varchar(15),
      email varchar(40),
      gender varchar(6),
      school varchar(50),
      address varchar(80),
      birth_year char(4),
      birth_month char(2),
      birth_day char(2),
      summary text,
      photo longblob
    );
