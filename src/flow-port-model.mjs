// Reference protocol model only; not an AttoLang runtime, borrow checker or guest ABI.
// Zero- or positive-capacity, single-consumer, demand-aware, ownership-ticketed port.
const PORT_AUTHORITY = Symbol('reference-model-port-authority');
const positive = (value, name) => {
  if (!Number.isSafeInteger(value) || value < 1) throw new RangeError(`${name} must be a positive safe integer`);
  return value;
};
const nonnegative = (value, name) => {
  if (!Number.isSafeInteger(value) || value < 0) throw new RangeError(`${name} must be a nonnegative safe integer`);
  return value;
};

export class OwnedValue {
  #owner = 'producer';
  #drops = 0;
  constructor(data, bytes) {
    this.data = data;
    Object.defineProperty(this, 'bytes', {value:positive(bytes, 'bytes'), enumerable:true, writable:false});
  }
  get owner() { return this.#owner; }
  get drops() { return this.#drops; }
  admit(authority) {
    if (authority !== PORT_AUTHORITY) throw new Error('unauthorized ownership transition');
    if (this.#owner !== 'producer') throw new Error('not producer-owned');
    this.#owner = 'port';
  }
  deliver(authority) {
    if (authority !== PORT_AUTHORITY) throw new Error('unauthorized ownership transition');
    if (this.#owner !== 'port') throw new Error('not port-owned');
    this.#owner = 'consumer';
  }
  drop(authority) {
    if (authority !== PORT_AUTHORITY) throw new Error('unauthorized ownership transition');
    if (this.#owner === 'dropped') throw new Error('double drop');
    if (this.#owner !== 'port') throw new Error('only port-owned values can be dropped by port');
    this.#owner = 'dropped';
    this.#drops++;
  }
}

export class FlowPortModel {
  constructor({capacity=2, maxBytes=1024, maxInFlight=2, maxDemand=1024}={}) {
    this.capacity = nonnegative(capacity, 'capacity');
    this.maxBytes = positive(maxBytes, 'maxBytes');
    this.maxInFlight = positive(maxInFlight, 'maxInFlight');
    this.maxDemand = positive(maxDemand, 'maxDemand');
    this.generation = 1;
    this.demand = 0;
    this.queued = [];
    this.ready = [];
    this.inFlight = new Map();
    this.chargedBytes = 0;
    this.nextTicket = 1;
    this.sealed = null;
    this.terminalDelivered = false;
  }
  _checkGeneration(generation) {
    if (generation !== this.generation) throw new Error('stale generation');
  }
  _dispatch() {
    while (this.demand > 0 && this.inFlight.size < this.maxInFlight && this.queued.length) {
      const value = this.queued.shift();
      this._deliver(value);
    }
    this._terminal();
  }
  _deliver(value) {
    if (this.demand === 0 || this.inFlight.size >= this.maxInFlight) throw new Error('no delivery credit');
    if (!Number.isSafeInteger(this.nextTicket)) throw new Error('ticket budget exhausted');
    const ticket = this.nextTicket++;
    this.demand--;
    value.deliver(PORT_AUTHORITY);
    this.inFlight.set(ticket, {value, generation: this.generation});
    this.ready.push({ticket, value, generation: this.generation});
  }
  _terminal() {
    if (this.sealed && this.queued.length === 0 && !this.terminalDelivered) {
      // Logically terminal after all NEXT deliveries have been admitted.
      // Physical reclamation still waits for inFlight acknowledgements.
      this.terminalDelivered = true;
    }
  }
  request(n, generation=this.generation) {
    this._checkGeneration(generation);
    positive(n, 'demand');
    if (this.sealed?.kind !== undefined && this.terminalDelivered) return {ok:false, reason:'terminal'};
    if (n > this.maxDemand - this.demand) return {ok:false, reason:'demand_overflow'};
    this.demand += n;
    this._dispatch();
    return {ok:true};
  }
  offer(value, generation=this.generation) {
    this._checkGeneration(generation);
    if (!(value instanceof OwnedValue) || value.owner !== 'producer') throw new TypeError('expected producer-owned value');
    if (this.sealed) return {ok:false, reason:'closed', value};
    if (!Number.isSafeInteger(this.nextTicket)) return {ok:false, reason:'ticket_exhausted', value};
    if (value.bytes > this.maxBytes - this.chargedBytes) return {ok:false, reason:'byte_budget', value};
    const canDeliver = this.demand > 0 && this.inFlight.size < this.maxInFlight && this.queued.length === 0;
    if (!canDeliver && this.queued.length >= this.capacity) return {ok:false, reason:'full', value};
    value.admit(PORT_AUTHORITY); // successful admission linearization point
    this.chargedBytes += value.bytes;
    if (canDeliver) this._deliver(value);
    else this.queued.push(value);
    return {ok:true};
  }
  takeReady(generation=this.generation) {
    this._checkGeneration(generation);
    const out = this.ready;
    this.ready = [];
    return out;
  }
  ack(ticket, generation=this.generation) {
    this._checkGeneration(generation);
    const item = this.inFlight.get(ticket);
    if (!item || item.generation !== generation) return {ok:false, reason:'unknown_ticket'};
    this.inFlight.delete(ticket);
    this.chargedBytes -= item.value.bytes;
    this._dispatch();
    return {ok:true};
  }
  complete() {
    if (this.sealed) return {ok:false, reason:'terminal_already_selected'};
    this.sealed = {kind:'complete'};
    this._dispatch();
    return {ok:true};
  }
  fail(error) {
    if (error === undefined) throw new TypeError('explicit error required');
    return this._abort({kind:'error', error});
  }
  cancel() { return this._abort({kind:'cancelled'}); }
  _abort(terminal) {
    if (this.sealed) return {ok:false, reason:'terminal_already_selected'};
    this.sealed = terminal;
    for (const value of this.queued) {
      this.chargedBytes -= value.bytes;
      value.drop(PORT_AUTHORITY);
    }
    this.queued = [];
    this._terminal();
    return {ok:true};
  }
  terminal() {
    return this.terminalDelivered ? this.sealed : null;
  }
  get quiescent() { return this.queued.length === 0 && this.inFlight.size === 0 && this.ready.length === 0 && this.chargedBytes === 0; }
  restart() {
    if (!this.sealed || !this.quiescent) return {ok:false, reason:'not_quiescent'};
    if (!Number.isSafeInteger(this.generation + 1)) return {ok:false, reason:'generation_exhausted'};
    this.generation++;
    this.demand = 0;
    this.sealed = null;
    this.terminalDelivered = false;
    return {ok:true, generation:this.generation};
  }
  snapshot() {
    return {generation:this.generation, queued:this.queued.length, inFlight:this.inFlight.size,
      ready:this.ready.length, chargedBytes:this.chargedBytes, demand:this.demand,
      terminal:this.terminal()?.kind ?? null, quiescent:this.quiescent};
  }
}
