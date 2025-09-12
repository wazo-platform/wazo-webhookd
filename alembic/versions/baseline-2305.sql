-- PostgreSQL database dump

-- Dumped from database version 13.18 (Debian 13.18-0+deb11u1)
-- Dumped by pg_dump version 13.18 (Debian 13.18-0+deb11u1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

-- Name: status_types; Type: TYPE; Schema: public; Owner: -

CREATE TYPE public.status_types AS ENUM (
    'success',
    'failure',
    'error'
);

SET default_tablespace = '';

SET default_table_access_method = heap;

-- Name: webhookd_subscription; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.webhookd_subscription (
    uuid character varying(38) DEFAULT public.uuid_generate_v4() NOT NULL,
    name text,
    service text,
    events_user_uuid character varying(36),
    owner_user_uuid character varying(36),
    events_wazo_uuid character varying(36),
    owner_tenant_uuid character varying(36) NOT NULL
);

-- Name: webhookd_subscription_event; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.webhookd_subscription_event (
    uuid character varying(38) DEFAULT public.uuid_generate_v4() NOT NULL,
    subscription_uuid character varying(38) NOT NULL,
    event_name text NOT NULL
);

-- Name: webhookd_subscription_log; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.webhookd_subscription_log (
    uuid character varying(36) NOT NULL,
    subscription_uuid character varying(38) NOT NULL,
    status public.status_types,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    attempts integer NOT NULL,
    max_attempts integer,
    event json,
    detail json
);

-- Name: webhookd_subscription_metadatum; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.webhookd_subscription_metadatum (
    uuid character varying(38) DEFAULT public.uuid_generate_v4() NOT NULL,
    subscription_uuid character varying(38) NOT NULL,
    key text NOT NULL,
    value text
);

-- Name: webhookd_subscription_option; Type: TABLE; Schema: public; Owner: -

CREATE TABLE public.webhookd_subscription_option (
    uuid character varying(38) DEFAULT public.uuid_generate_v4() NOT NULL,
    subscription_uuid character varying(38) NOT NULL,
    name text NOT NULL,
    value text
);

-- Data for Name: webhookd_subscription; Type: TABLE DATA; Schema: public; Owner: -

-- Data for Name: webhookd_subscription_event; Type: TABLE DATA; Schema: public; Owner: -

-- Data for Name: webhookd_subscription_log; Type: TABLE DATA; Schema: public; Owner: -

-- Data for Name: webhookd_subscription_metadatum; Type: TABLE DATA; Schema: public; Owner: -

-- Data for Name: webhookd_subscription_option; Type: TABLE DATA; Schema: public; Owner: -

-- Name: webhookd_subscription_event webhookd_subscription_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_event
    ADD CONSTRAINT webhookd_subscription_event_pkey PRIMARY KEY (uuid);

-- Name: webhookd_subscription_event webhookd_subscription_event_subscription_uuid_event_name_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_event
    ADD CONSTRAINT webhookd_subscription_event_subscription_uuid_event_name_key UNIQUE (subscription_uuid, event_name);

-- Name: webhookd_subscription_log webhookd_subscription_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_log
    ADD CONSTRAINT webhookd_subscription_log_pkey PRIMARY KEY (uuid, attempts);

-- Name: webhookd_subscription_metadatum webhookd_subscription_metadatum_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_metadatum
    ADD CONSTRAINT webhookd_subscription_metadatum_pkey PRIMARY KEY (uuid);

-- Name: webhookd_subscription_option webhookd_subscription_option_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_option
    ADD CONSTRAINT webhookd_subscription_option_pkey PRIMARY KEY (uuid);

-- Name: webhookd_subscription_option webhookd_subscription_option_subscription_uuid_name_key; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_option
    ADD CONSTRAINT webhookd_subscription_option_subscription_uuid_name_key UNIQUE (subscription_uuid, name);

-- Name: webhookd_subscription webhookd_subscription_pkey; Type: CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription
    ADD CONSTRAINT webhookd_subscription_pkey PRIMARY KEY (uuid);

-- Name: webhookd_subscription_event__idx__subscription_uuid; Type: INDEX; Schema: public; Owner: -

CREATE INDEX webhookd_subscription_event__idx__subscription_uuid ON public.webhookd_subscription_event USING btree (subscription_uuid);

-- Name: webhookd_subscription_log__idx__subscription_uuid; Type: INDEX; Schema: public; Owner: -

CREATE INDEX webhookd_subscription_log__idx__subscription_uuid ON public.webhookd_subscription_log USING btree (subscription_uuid);

-- Name: webhookd_subscription_metadatum__idx__subscription_uuid; Type: INDEX; Schema: public; Owner: -

CREATE INDEX webhookd_subscription_metadatum__idx__subscription_uuid ON public.webhookd_subscription_metadatum USING btree (subscription_uuid);

-- Name: webhookd_subscription_option__idx__subscription_uuid; Type: INDEX; Schema: public; Owner: -

CREATE INDEX webhookd_subscription_option__idx__subscription_uuid ON public.webhookd_subscription_option USING btree (subscription_uuid);

-- Name: webhookd_subscription_event webhookd_subscription_event_subscription_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_event
    ADD CONSTRAINT webhookd_subscription_event_subscription_uuid_fkey FOREIGN KEY (subscription_uuid) REFERENCES public.webhookd_subscription(uuid) ON DELETE CASCADE;

-- Name: webhookd_subscription_log webhookd_subscription_log_subscription_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_log
    ADD CONSTRAINT webhookd_subscription_log_subscription_uuid_fkey FOREIGN KEY (subscription_uuid) REFERENCES public.webhookd_subscription(uuid) ON DELETE CASCADE;

-- Name: webhookd_subscription_metadatum webhookd_subscription_metadatum_subscription_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_metadatum
    ADD CONSTRAINT webhookd_subscription_metadatum_subscription_uuid_fkey FOREIGN KEY (subscription_uuid) REFERENCES public.webhookd_subscription(uuid) ON DELETE CASCADE;

-- Name: webhookd_subscription_option webhookd_subscription_option_subscription_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -

ALTER TABLE ONLY public.webhookd_subscription_option
    ADD CONSTRAINT webhookd_subscription_option_subscription_uuid_fkey FOREIGN KEY (subscription_uuid) REFERENCES public.webhookd_subscription(uuid) ON DELETE CASCADE;

-- PostgreSQL database dump complete
