-- seed.sql — Demo-Daten für XOS
-- Tabellen anlegen und mit internationalen Beispieldaten befüllen.
-- Idempotent: kann beliebig oft ausgeführt werden (löscht vorher alles).

-- ── Schema ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.person (
    id        serial4      NOT NULL,
    firstname varchar(100) NOT NULL,
    lastname  varchar(100) NOT NULL,
    age       int4         NULL,
    net_worth float8       NULL,
    street    varchar(100) NULL,
    zip       varchar(10)  NULL,
    city      varchar(100) NULL,
    email     varchar(100) NULL,
    phone     varchar(20)  NULL,
    CONSTRAINT person_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.note (
    id         serial4      NOT NULL,
    person_id  int4         NOT NULL,
    created_at timestamptz  DEFAULT now() NOT NULL,
    title      varchar(200) NOT NULL,
    body       text         NULL,
    CONSTRAINT note_pkey PRIMARY KEY (id)
);

ALTER TABLE public.note
    DROP CONSTRAINT IF EXISTS note_person_id_fkey;
ALTER TABLE public.note
    ADD CONSTRAINT note_person_id_fkey
    FOREIGN KEY (person_id) REFERENCES public.person(id);

-- ── Demo-Daten: Personen ──────────────────────────────────────────────────────

TRUNCATE public.note, public.person RESTART IDENTITY CASCADE;

INSERT INTO public.person (firstname, lastname, age, net_worth, street, zip, city, email, phone) VALUES
    ('Sophie',    'Martin',     34,  125000.00, '12 Rue de Rivoli',      '75001', 'Paris',        'sophie.martin@example.com',    '+33 1 23456789'),
    ('James',     'Thompson',   50,    4806.00, '47 Baker Street',       'W1U 7BJ','London',       'james.thompson@example.com',   '+44 20 79460000'),
    ('Yuki',      'Tanaka',     26,       0.00, 'Shibuya 3-12-5',        '150-0002','Tokyo',       'yuki.tanaka@example.com',      '+81 3 12345678'),
    ('Michael',   'OBrien',     60,    1251.00, '88 Collins Street',     '3000',  'Melbourne',     'michael.obrien@example.com',   '+61 3 98765432'),
    ('Amira',     'Hassan',     46,  320000.75, 'Al Wasl Road 22',       '00000', 'Dubai',         'amira.hassan@example.com',     '+971 4 3456789'),
    ('Lars',      'Eriksson',   74, 2100000.00, 'Kungsgatan 9',          '11143', 'Stockholm',     'lars.eriksson@example.com',    '+46 8 123456'),
    ('Valentina', 'Rossi',      31,   54000.00, 'Via Condotti 3',        '00187', 'Rome',          'valentina.rossi@example.com',  '+39 06 12345678'),
    ('Daniel',    'Kowalski',   48,  780000.00, 'ul. Nowy Świat 6',      '00-400','Warsaw',        'daniel.kowalski@example.com',  '+48 22 8765432'),
    ('Lin',       'Wei',        45, 1650000.00, 'Nanjing Road 18',       '200001','Shanghai',      'lin.wei@example.com',          '+86 21 63219876'),
    ('Carlos',    'Mendoza',    22,   12000.00, 'Av. Insurgentes Sur 5', '06600', 'Mexico City',   'carlos.mendoza@example.com',   '+52 55 12345678'),
    ('Priya',     'Sharma',     66, 3400000.00, 'MG Road 11',            '560001','Bangalore',     'priya.sharma@example.com',     '+91 80 22334455'),
    ('Fatima',    'Al-Rashid',  50,  420000.00, 'King Fahd Road 33',     '11564', 'Riyadh',        'fatima.alrashid@example.com',  '+966 11 2345678'),
    ('Emma',      'Johansson',  58,  890000.00, 'Drottninggatan 3',      '41103', 'Gothenburg',    'emma.johansson@example.com',   '+46 31 987654'),
    ('Robert',    'Nkosi',      75, 5600000.00, 'Sandton Drive 17',      '2196',  'Johannesburg',  'robert.nkosi@example.com',     '+27 11 8765432'),
    ('Clara',     'Dubois',     24,       0.00, 'Rue Neuve 8',           '1000',  'Brussels',      'clara.dubois@example.com',     '+32 2 5551234');

-- ── Demo-Daten: Notizen ───────────────────────────────────────────────────────

INSERT INTO public.note (person_id, title, body) VALUES
    (1,  'Erstgespräch verschoben',          'Interesse an ETF-Sparplan geäußert. Folgetermin in vier Wochen.'),
    (2,  'Dokumente angefordert',             'Gehaltsnachweis und Kontoauszüge fehlen noch.'),
    (2,  'Steuerberatung koordiniert',        'Kontakt zu Steuerberater Dr. Hassan hergestellt.'),
    (3,  'Portfolioüberprüfung',              'Bestandsportfolio auf Immobilienlastigkeit geprüft. Diversifikation empfohlen.'),
    (4,  'VIP Status bestätigt',              'Kunde seit 2015. Bevorzugte Kommunikation per E-Mail.'),
    (4,  'Nachfolgeplanung',                  'Gespräch über Vermögensübertragung vereinbart.'),
    (6,  'Risikohinweis erteilt',             'Aufgrund des Alters auf konservative Anlageformen hingewiesen.'),
    (6,  'Testament erwähnt',                 'Kunde erwähnte laufende notarielle Regelung.'),
    (7,  'Budgetberatung',                    'Monatliche Sparrate von 300 € vereinbart.'),
    (8,  'Immobilienfinanzierung',            'Anfrage für Anschlussfinanzierung bis Q3 2025.'),
    (8,  'Rückruf ausstehend',               'Keine Erreichbarkeit seit 14 Tagen.'),
    (11, 'Jahresgespräch',                    'Sehr zufrieden mit Betreuung. Empfehlung an Bekannte zugesagt.'),
    (10, 'Junges Kundenprofil',               'Student. Interesse an erstem Depot. Niedrigschwellige Einstiegslösung besprochen.'),
    (15, 'Onboarding',                        'Neukundin seit Januar. Kontoeröffnung abgeschlossen.');
