-- =====================================================================
-- NEXUS v3 — Esquema limpio (instalación desde cero)
-- Compatible con MariaDB 10.4 (XAMPP) y MySQL 8. Idempotente.
-- Uso:  mysql -u root < nexus_v3.sql      (o importarlo en phpMyAdmin)
-- Si ya tienes datos que quieras conservar, haz respaldo antes.
-- =====================================================================
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Tablas viejas que reemplaza este esquema (la `actividades` vieja guardaba
-- el nombre del residente como texto; ahora `actividades` es el catálogo).
DROP TABLE IF EXISTS agenda_eventos;
DROP TABLE IF EXISTS medicamento_horas;
DROP TABLE IF EXISTS medicamentos_residente;
DROP TABLE IF EXISTS catalogo_medicamentos;
DROP TABLE IF EXISTS actividades;

-- ---------------------------------------------------------------------
-- 1) Usuarios, personal, residentes (sin cambios de nombre)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
  id       INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(191) NOT NULL,
  password VARCHAR(255) NOT NULL,
  rol      VARCHAR(100) NOT NULL DEFAULT 'Cuidador',   -- Administrador | Cuidador (enfermero) | Familiar
  nombre   VARCHAR(255) DEFAULT NULL,
  correo   VARCHAR(255) DEFAULT NULL,
  UNIQUE KEY uq_usuarios_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS residentes (
  id                  INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nombre              VARCHAR(255) NOT NULL,
  documento           VARCHAR(100) NOT NULL,
  edad                INT DEFAULT NULL,
  fecha_ingreso       VARCHAR(30) DEFAULT NULL,
  habitacion          VARCHAR(100) DEFAULT NULL,
  diagnostico         TEXT DEFAULT NULL,
  medicamentos        TEXT DEFAULT NULL,
  alergias            TEXT DEFAULT NULL,
  familiar_nombre     VARCHAR(255) DEFAULT NULL,
  familiar_parentesco VARCHAR(100) DEFAULT NULL,
  familiar_telefono   VARCHAR(100) DEFAULT NULL,
  familiar_username   VARCHAR(191) DEFAULT NULL,
  UNIQUE KEY uq_residentes_documento (documento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS personal (
  id         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nombre     VARCHAR(255) NOT NULL,
  correo     VARCHAR(255) DEFAULT NULL,
  telefono   VARCHAR(100) DEFAULT NULL,
  turno      VARCHAR(100) DEFAULT NULL,
  activo     TINYINT NOT NULL DEFAULT 1,
  usuario_id INT DEFAULT NULL,
  KEY idx_personal_usuario (usuario_id),
  CONSTRAINT fk_personal_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS asignaciones (
  id               INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  residente_id     INT NOT NULL,
  personal_id      INT NOT NULL,
  fecha_asignacion DATE NOT NULL DEFAULT (CURDATE()),
  UNIQUE KEY uq_asignacion (residente_id, personal_id),
  KEY idx_asig_personal (personal_id),
  CONSTRAINT fk_asig_residente FOREIGN KEY (residente_id) REFERENCES residentes (id) ON DELETE CASCADE,
  CONSTRAINT fk_asig_personal  FOREIGN KEY (personal_id)  REFERENCES personal (id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 2) Catálogos: categoría 1:N medicamentos / actividades
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias_medicamentos (
  id     INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  activo TINYINT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catmed_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS medicamentos (
  id           INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  categoria_id INT NOT NULL,
  nombre       VARCHAR(191) NOT NULL,
  presentacion VARCHAR(100) DEFAULT NULL,
  activo       TINYINT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_med_cat_nombre (categoria_id, nombre),
  CONSTRAINT fk_med_categoria FOREIGN KEY (categoria_id)
    REFERENCES categorias_medicamentos (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS categorias_actividades (
  id     INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  activo TINYINT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_catact_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS actividades (
  id           INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  categoria_id INT NOT NULL,
  nombre       VARCHAR(191) NOT NULL,
  activo       TINYINT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_act_cat_nombre (categoria_id, nombre),
  CONSTRAINT fk_act_categoria FOREIGN KEY (categoria_id)
    REFERENCES categorias_actividades (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 3) Itinerario diario: UNA fila por (residente, día, medicamento|actividad)
--    con todas las horas en un arreglo JSON  ["06:00","12:00"]
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS itinerario_diario (
  id            INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  residente_id  INT NOT NULL,
  fecha         DATE NOT NULL,
  tipo          ENUM('medicamento','actividad') NOT NULL,
  medicamento_id INT DEFAULT NULL,
  actividad_id   INT DEFAULT NULL,
  dosis         VARCHAR(100) DEFAULT NULL,            -- solo medicamentos
  horas         JSON NOT NULL,                        -- ["06:00","12:00"]
  observaciones TEXT DEFAULT NULL,                    -- textarea amplio
  personal_id   INT DEFAULT NULL,
  creado_por    INT DEFAULT NULL,
  creado_en     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_itin_res_fecha (residente_id, fecha),
  KEY idx_itin_personal_fecha (personal_id, fecha),
  CONSTRAINT fk_itin_residente FOREIGN KEY (residente_id)   REFERENCES residentes (id)   ON DELETE CASCADE,
  CONSTRAINT fk_itin_med       FOREIGN KEY (medicamento_id) REFERENCES medicamentos (id) ON DELETE RESTRICT,
  CONSTRAINT fk_itin_act       FOREIGN KEY (actividad_id)   REFERENCES actividades (id)  ON DELETE RESTRICT,
  CONSTRAINT fk_itin_personal  FOREIGN KEY (personal_id)    REFERENCES personal (id)     ON DELETE SET NULL,
  CONSTRAINT fk_itin_creador   FOREIGN KEY (creado_por)     REFERENCES usuarios (id)     ON DELETE SET NULL,
  CONSTRAINT ck_itin_tipo CHECK (
    (tipo = 'medicamento' AND medicamento_id IS NOT NULL AND actividad_id IS NULL) OR
    (tipo = 'actividad'   AND actividad_id   IS NOT NULL AND medicamento_id IS NULL)
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ✓ por hora: si existe la fila = completado (✓); si no existe = pendiente (✗)
CREATE TABLE IF NOT EXISTS itinerario_checks (
  itinerario_id  INT NOT NULL,
  hora           CHAR(5) NOT NULL,                    -- 'HH:MM', debe estar en itinerario_diario.horas
  completado_por INT DEFAULT NULL,
  completado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (itinerario_id, hora),
  CONSTRAINT fk_chk_itin FOREIGN KEY (itinerario_id) REFERENCES itinerario_diario (id) ON DELETE CASCADE,
  CONSTRAINT fk_chk_user FOREIGN KEY (completado_por) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Observaciones generales del día del residente (textarea grande del calendario)
CREATE TABLE IF NOT EXISTS itinerario_observaciones (
  residente_id INT NOT NULL,
  fecha        DATE NOT NULL,
  texto        TEXT NOT NULL,
  actualizado_por INT DEFAULT NULL,
  actualizado_en  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (residente_id, fecha),
  CONSTRAINT fk_iobs_res  FOREIGN KEY (residente_id)    REFERENCES residentes (id) ON DELETE CASCADE,
  CONSTRAINT fk_iobs_user FOREIGN KEY (actualizado_por) REFERENCES usuarios (id)   ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 4) Historial, notificaciones, recuperación de contraseña (igual que antes)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial (
  id        INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  fecha     VARCHAR(30) NOT NULL,
  hora      VARCHAR(30) NOT NULL,
  tipo      VARCHAR(100) NOT NULL,
  actividad TEXT NOT NULL,
  residente VARCHAR(255) NOT NULL,
  cuidador  VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notificaciones (
  id        INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  residente VARCHAR(255) NOT NULL,
  tipo      VARCHAR(100) NOT NULL,
  detalle   TEXT DEFAULT NULL,
  fecha     VARCHAR(30) NOT NULL,
  hora      VARCHAR(30) NOT NULL,
  estado    VARCHAR(100) NOT NULL DEFAULT 'Pendiente',
  mostrada  TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notificaciones_generadas (
  id        INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  residente VARCHAR(255) NOT NULL,
  tipo      VARCHAR(100) NOT NULL,
  detalle   VARCHAR(255) DEFAULT NULL,
  fecha     VARCHAR(30) NOT NULL,
  hora      VARCHAR(30) NOT NULL,
  UNIQUE KEY uq_notificacion_generada (residente, tipo, fecha, hora, detalle)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS codigos_verificacion (
  id         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario_id INT NOT NULL,
  codigo     VARCHAR(255) NOT NULL,
  creado     VARCHAR(40) NOT NULL,
  expira     VARCHAR(40) NOT NULL,
  usado      TINYINT NOT NULL DEFAULT 0,
  KEY idx_codigo_usuario (usuario_id),
  CONSTRAINT fk_codigo_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 5) Datos iniciales
-- ---------------------------------------------------------------------
INSERT IGNORE INTO categorias_medicamentos (id, nombre) VALUES
  (1,'General'),(2,'Diabetes'),(3,'Cardiovascular'),(4,'Salud mental / Neurología'),
  (5,'Digestivo'),(6,'Respiratorio'),(7,'Suplementos');

INSERT IGNORE INTO medicamentos (categoria_id, nombre) VALUES
  (1,'Acetaminofén (paracetamol)'),(1,'Amoxicilina'),
  (2,'Insulina'),(2,'Metformina'),
  (3,'Losartán'),(3,'Amlodipino'),(3,'Enalapril'),(3,'Atorvastatina'),(3,'Furosemida'),
  (3,'Ácido acetilsalicílico (AAS)'),(3,'Clopidogrel'),(3,'Apixabán'),
  (4,'Sertralina'),(4,'Trazodona'),(4,'Donepezilo'),(4,'Memantina'),
  (5,'Omeprazol'),(5,'Polietilenglicol (PEG)'),(5,'Lactulosa'),
  (6,'Salbutamol'),
  (7,'Carbonato de calcio'),(7,'Vitamina D'),(7,'Hierro oral'),(7,'Levotiroxina');

INSERT IGNORE INTO categorias_actividades (id, nombre) VALUES
  (1,'Fisioterapia'),(2,'Recreación'),(3,'Higiene y cuidado'),(4,'Alimentación'),(5,'Estimulación cognitiva');

INSERT IGNORE INTO actividades (categoria_id, nombre) VALUES
  (1,'Ejercicios de movilidad'),(1,'Caminata asistida'),(1,'Estiramientos'),
  (2,'Yoga'),(2,'Música'),(2,'Juegos de mesa'),
  (3,'Baño asistido'),(3,'Cambio de posición'),(3,'Cuidado de piel'),
  (4,'Desayuno'),(4,'Almuerzo'),(4,'Cena'),
  (5,'Lectura'),(5,'Crucigramas'),(5,'Memoria y rompecabezas');

-- Usuarios de prueba (mismas contraseñas hasheadas de tu dump: SHA-256)
INSERT IGNORE INTO usuarios (id, username, password, rol, nombre) VALUES
  (1,'admin','240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9','Administrador','Administrador'),
  (4,'cuidador','781de0a8a22dd49b8807c47558af8f97efdfde1b588ba7390ba0a139d123f93a','Cuidador','Cuidador de prueba'),
  (5,'familiar','15a91af54762d7da06cb968b7dd8cbc1986923b3477c41b2834b464dd12043f6','Familiar','Familiar de prueba');

INSERT IGNORE INTO personal (id, nombre, correo, telefono, turno, activo, usuario_id) VALUES
  (2,'Cuidador de prueba','cuidador@gmail.com','3242428419','Mañana',1,4);

INSERT IGNORE INTO residentes (id, nombre, documento, edad, fecha_ingreso, habitacion, diagnostico, medicamentos, alergias,
                               familiar_nombre, familiar_parentesco, familiar_telefono, familiar_username) VALUES
  (2,'Rosa Elena Gómez','1000111222',78,'2026-09-03','204','Hipertensión','Losartán 50mg','Ninguna conocida',
   'Familiar de prueba','Hija','3001234567','familiar');

INSERT IGNORE INTO asignaciones (residente_id, personal_id) VALUES (2,2);
