-- Скрипт инициализации PostgreSQL

-- Обновляем пароль для пользователя postgres (или создаем, если не существует)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='postgres') THEN
        CREATE USER postgres WITH PASSWORD '1234';
        ALTER USER postgres WITH SUPERUSER;
    ELSE
        ALTER USER postgres WITH PASSWORD '1234';
        ALTER USER postgres WITH SUPERUSER;
    END IF;
END
$$;