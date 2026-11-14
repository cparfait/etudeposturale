// Capteurs Bluetooth (Web Bluetooth, Chrome/Edge) : cardio, puissance (Assioma), home trainer (Tacx Neo 2T).
// Protocoles : Heart Rate Service, Cycling Power Service, Tacx FE-C sur BLE (repli : FTMS).
// ⚠ Écrit d'après les spécifications Bluetooth SIG / ANT+ FE-C ; non testé sur le matériel réel.
/* eslint-disable @typescript-eslint/no-explicit-any */

export const FEC_SERVICE = "6e40fec1-b5a3-f393-e0a9-e50e24dcca9e";
const FEC_WRITE = "6e40fec3-b5a3-f393-e0a9-e50e24dcca9e";

export const bluetoothAvailable = () => typeof navigator !== "undefined" && "bluetooth" in navigator;

async function connect(filters: any[], optionalServices: any[] = []) {
  const device = await (navigator as any).bluetooth.requestDevice({ filters, optionalServices });
  const server = await device.gatt.connect();
  return { device, server };
}

/** Fréquence cardiaque (bpm). */
export async function connectHeartRate(onValue: (bpm: number) => void) {
  const { device, server } = await connect([{ services: ["heart_rate"] }]);
  const ch = await (await server.getPrimaryService("heart_rate")).getCharacteristic("heart_rate_measurement");
  ch.addEventListener("characteristicvaluechanged", (e: any) => onValue(parseHeartRate(e.target.value)));
  await ch.startNotifications();
  return device;
}

export function parseHeartRate(v: DataView): number {
  return v.getUint8(0) & 0x01 ? v.getUint16(1, true) : v.getUint8(1);
}

export interface PowerSample { power: number; balanceLeft: number | null; cadence: number | null }

/** Puissance, équilibre G/D (si fourni) et cadence (données de pédalier). */
export async function connectPower(onValue: (s: PowerSample) => void) {
  const { device, server } = await connect([{ services: ["cycling_power"] }]);
  const ch = await (await server.getPrimaryService("cycling_power")).getCharacteristic("cycling_power_measurement");
  const state = { revs: null as number | null, time: null as number | null, cadence: null as number | null };
  ch.addEventListener("characteristicvaluechanged", (e: any) => onValue(parsePower(e.target.value, state)));
  await ch.startNotifications();
  return device;
}

export function parsePower(v: DataView, st: { revs: number | null; time: number | null; cadence: number | null }): PowerSample {
  const flags = v.getUint16(0, true);
  const power = v.getInt16(2, true);
  let o = 4, balanceLeft: number | null = null;
  if (flags & 0x01) {               // Pedal Power Balance (0,5 %)
    const pct = v.getUint8(o) / 2;
    balanceLeft = flags & 0x02 ? pct : 100 - pct; // bit 1 : référence = gauche
    o += 1;
  }
  if (flags & 0x04) o += 2;         // Accumulated Torque
  if (flags & 0x10) o += 6;         // Wheel Revolution Data
  if (flags & 0x20) {               // Crank Revolution Data → cadence
    const revs = v.getUint16(o, true), time = v.getUint16(o + 2, true);
    if (st.revs != null && st.time != null) {
      const dr = (revs - st.revs + 65536) % 65536;
      const dt = ((time - st.time + 65536) % 65536) / 1024;
      if (dt > 0 && dr > 0) st.cadence = Math.round((dr / dt) * 60);
      else if (dt > 2) st.cadence = 0;
    }
    st.revs = revs; st.time = time;
  }
  return { power, balanceLeft, cadence: st.cadence };
}

/** Message ANT FE-C page 49 (puissance cible, unités de 0,25 W), encapsulé pour le service Tacx BLE. */
export function fecTargetPower(watts: number): Uint8Array {
  const q = Math.max(0, Math.min(4000, Math.round(watts * 4)));
  const msg = [0xa4, 0x09, 0x4f, 0x05, 0x31, 0xff, 0xff, 0xff, 0xff, 0xff, q & 0xff, (q >> 8) & 0xff];
  msg.push(msg.reduce((a, b) => a ^ b, 0));
  return new Uint8Array(msg);
}

export interface Trainer { device: any; setPower: (w: number) => Promise<void>; protocol: "FE-C" | "FTMS" }

/** Home trainer : Tacx FE-C sur BLE si disponible, sinon FTMS (Fitness Machine Service). */
export async function connectTrainer(): Promise<Trainer> {
  const { device, server } = await connect(
    [{ services: [FEC_SERVICE] }, { services: ["fitness_machine"] }, { namePrefix: "Tacx" }],
    [FEC_SERVICE, "fitness_machine", "cycling_power"],
  );
  try {
    const svc = await server.getPrimaryService(FEC_SERVICE);
    const ch = await svc.getCharacteristic(FEC_WRITE);
    return { device, protocol: "FE-C", setPower: async (w) => ch.writeValue(fecTargetPower(w)) };
  } catch {
    const svc = await server.getPrimaryService("fitness_machine");
    const cp = await svc.getCharacteristic("fitness_machine_control_point");
    await cp.startNotifications();
    await cp.writeValue(new Uint8Array([0x00])); // Request Control
    return {
      device, protocol: "FTMS",
      setPower: async (w) => {
        const v = Math.round(w);
        await cp.writeValue(new Uint8Array([0x05, v & 0xff, (v >> 8) & 0xff])); // Set Target Power
      },
    };
  }
}
