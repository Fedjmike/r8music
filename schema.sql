drop table if exists artists;
create table artists (
    id integer primary key autoincrement,
    name text not null,
    slug text not null
);

drop table if exists releases;
create table releases (
    id integer primary key autoincrement,
    artist_id integer not null,
    title text not null,
    slug text not null,
    'date' text not null,
    type text not null,
    album_art_url text

);

drop table if exists tracks;
create table tracks (
    id integer primary key autoincrement,
    release_id integer not null,
    title text not null,
    slug text not null,
    position integer not null,
    runtime integer not null
);

drop table if exists release_colors;
create table release_colors (
    release_id integer primary key,
    color1 text not null,
    color2 text not null,
    color3 text not null
);
