-- Music objects

drop table if exists objects;
create table objects (
    id integer primary key,
    type int not null -- model.ObjectType enum
);

drop table if exists artists;
create table artists (
    id integer not null,
    name text not null,
    slug text not null,
    incomplete text,
    foreign key (id) references objects(id)
);

create index artist_id_index on artists(id);
create index artist_slug_index on artists(slug);

drop table if exists releases;
create table releases (
    id integer not null,
    title text not null,
    slug text not null,
    date text not null, -- ISO 8601 date
    type text not null,
    full_art_url text,
    thumb_art_url text,
    foreign key (id) references objects(id)
);

create index release_id_index on releases(id);
create index release_slug_index on releases(slug);

drop table if exists authorships;
create table authorships (
    release_id integer not null,
    artist_id integer not null,
    primary key (release_id, artist_id),
    foreign key (release_id) references releases(id),
    foreign key (artist_id) references artists(id)
);

create index authorship_index on authorships(release_id, artist_id);
create index authorship_artist_index on authorships(artist_id);

drop table if exists tracks;
create table tracks (
    id integer not null,
    release_id integer not null,
    title text not null,
    slug text not null,
    position integer not null,
    side integer not null,
    runtime integer, -- In milliseconds
    foreign key (id) references objects(id)
);

create index track_release_index on tracks(release_id);

-- Object attachments

drop table if exists palettes;
create table palettes (
    id integer primary key,
    -- As an #rrggbb hex code, inc. hash
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

create index description_id_index on descriptions(id);

drop table if exists links;
create table links (
    id integer not null,
    type_id text not null,
    target text not null,
    primary key (id, type_id),
    foreign key (id) references objects(id),
    foreign key (type_id) references link_types(id)
);

drop table if exists link_types;
create table link_types (
    id integer primary key,
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
    creation text not null -- ISO 8601 date
);

create index user_name_index on users(name);

drop table if exists user_timezones;
create table user_timezones (
    user_id integer primary key,
    timezone text not null, -- [+-]\d\d:\d\d
    foreign key (user_id) references users(id)
);

drop table if exists user_rating_descriptions;
create table user_rating_descriptions (
    user_id integer not null,
    rating integer not null,
    description text not null,
    foreign key (user_id) references users(id)
);

create index user_rating_description_index on user_rating_descriptions(user_id, rating);

-- Actions

drop table if exists actions;
create table actions (
    id integer primary key,
    user_id integer not null,
    object_id integer not null,
    type integer not null, -- model.ActionType enum
    creation text not null, -- ISO 8601 date
    foreign key (user_id) references users(id),
    foreign key (object_id) references objects(id)
);

drop table if exists ratings;
create table ratings (
    action_id integer not null,
    rating integer not null,
    foreign key (action_id) references actions(id)
);

create index rating_id_index on ratings(action_id);
