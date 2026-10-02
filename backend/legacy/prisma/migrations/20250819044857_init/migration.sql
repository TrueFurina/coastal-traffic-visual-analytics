-- CreateTable
CREATE TABLE "Ship" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "name" TEXT NOT NULL,
    "mmsi" TEXT NOT NULL,
    "imo" TEXT,
    "ship_type" TEXT,
    "length" REAL,
    "width" REAL,
    "draft" REAL,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" DATETIME
);

-- CreateTable
CREATE TABLE "ShipTrack" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ship_id" INTEGER NOT NULL,
    "timestamp" DATETIME NOT NULL,
    "longitude" REAL NOT NULL,
    "latitude" REAL NOT NULL,
    "course" REAL,
    "speed" REAL,
    "heading" REAL,
    "status" TEXT,
    CONSTRAINT "ShipTrack_ship_id_fkey" FOREIGN KEY ("ship_id") REFERENCES "Ship" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Ship_mmsi_key" ON "Ship"("mmsi");

-- CreateIndex
CREATE INDEX "ShipTrack_ship_id_idx" ON "ShipTrack"("ship_id");

-- CreateIndex
CREATE INDEX "ShipTrack_timestamp_idx" ON "ShipTrack"("timestamp");

-- CreateIndex
CREATE INDEX "ShipTrack_ship_id_timestamp_idx" ON "ShipTrack"("ship_id", "timestamp");
