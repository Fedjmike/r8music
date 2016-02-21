drop table if exists artists;
create table artists (
    id integer primary key autoincrement,
    name text not null,
    slug text not null,
    incomplete text
);

drop table if exists releases;
create table releases (
    id integer primary key autoincrement,
    title text not null,
    slug text not null,
    'date' text not null,
    type text not null,
    full_art_url text,
    thumb_art_url text
);

drop table if exists release_mbid;
create table release_mbid (
    release_id integer not null,
    mbid text not null,
    foreign key(release_id) references releases(id)
);

drop table if exists authorships;
create table authorships (
    release_id integer not null,
    artist_id integer not null,
    primary key (release_id, artist_id),
    foreign key(release_id) references releases(id),
    foreign key(artist_id) references artists(id)
);


drop table if exists tracks;
create table tracks (
    id integer primary key autoincrement,
    release_id integer not null,
    title text not null,
    slug text not null,
    position integer not null,
    runtime integer
);

drop table if exists release_colors;
create table release_colors (
    release_id integer primary key,
    color1 text,
    color2 text,
    color3 text
);

drop table if exists users;
create table users (
    id integer primary key autoincrement,
    name text not null,
    pw_hash text not null,
    email text,
    fullname text,
    creation text not null
);

drop table if exists ratings;
create table ratings (
    release_id integer not null,
    user_id integer not null,
    rating integer not null,
    creation text not null,
    primary key (release_id, user_id)
);
