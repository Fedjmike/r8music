drop table if exists artists;
create table artists (
    id integer primary key autoincrement,
    name text not null,
    slug text not null
);

drop table if exists releases;
create table releases (
    id integer primary key autoincrement,
    title text not null,
    'date' text not null,
	artist_id integer not null,
    type text not null,
    slug text not null

);

drop table if exists tracks;
create table tracks (
    id integer primary key autoincrement,
    position integer not null,
    title text not null,
    runtime integer not null,
	release_id integer not null,
    slug text not null
);
