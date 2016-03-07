-- Music objects

drop table if exists objects;
create table objects (
    id integer primary key,
    type int not null
);

drop table if exists artists;
create table artists (
    id integer not null,
    name text not null,
    slug text not null,
    incomplete text,
    foreign key (id) references objects(id)
);

drop table if exists releases;
create table releases (
    id integer not null,
    title text not null,
    slug text not null,
    date text not null,
    type text not null,
    full_art_url text,
    thumb_art_url text,
    foreign key (id) references objects(id)
);

drop table if exists authorships;
create table authorships (
    release_id integer not null,
    artist_id integer not null,
    primary key (release_id, artist_id),
    foreign key (release_id) references releases(id),
    foreign key (artist_id) references artists(id)
);

drop table if exists tracks;
create table tracks (
    id integer not null,
    release_id integer not null,
    title text not null,
    slug text not null,
    position integer not null,
    runtime integer,
    foreign key (id) references objects(id)
);

-- Object attachments

drop table if exists palettes;
create table palettes (
    id integer primary key,
    color1 text,
    color2 text,
    color3 text,
    foreign key (id) references objects(id)
);

drop table if exists descriptions;
create table descriptions (
    id integer not null,
    description text,
    foreign key (id) references objects(id)
);

drop table if exists links;
create table links (
    id integer not null,
    type_id text not null,
    target text not null,
    primary key (id, type_id),
    foreign key (id) references objects(id)
    foreign key (type_id) references link_types(id)
);

drop table if exists link_types;
create table link_types (
    id integer primary key autoincrement,
    type text not null
);

-- Users

drop table if exists users;
create table users (
    id integer primary key,
    name text not null,
    pw_hash text not null,
    email text,
    fullname text,
    creation text not null
);

drop table if exists ratings;
create table ratings (
    object_id integer not null,
    user_id integer not null,
    rating integer not null,
    creation text not null,
    primary key (object_id, user_id)
    foreign key (object_id) references objects(id),
    foreign key (user_id) references users(id)
);
