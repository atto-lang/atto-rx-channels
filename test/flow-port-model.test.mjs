import test from 'node:test';
import assert from 'node:assert/strict';
import {FlowPortModel, OwnedValue} from '../src/flow-port-model.mjs';
const owned = (data,bytes=1) => new OwnedValue(data,bytes);

test('pull/demand: no unsolicited NEXT and FIFO across queued/ready values', () => {
  const p = new FlowPortModel({capacity:2, maxInFlight:2});
  const a=owned('a'),b=owned('b');
  assert.equal(p.offer(a).ok,true); assert.equal(p.offer(b).ok,true);
  assert.deepEqual(p.takeReady(),[]);
  assert.equal(p.request(1).ok,true);
  const [one]=p.takeReady();
  assert.equal(one.value,a); assert.equal(a.owner,'consumer');
  assert.equal(p.request(1).ok,true);
  const [two]=p.takeReady(); assert.equal(two.value,b);
  assert.ok(one.ticket!==two.ticket);
  assert.equal(p.ack(one.ticket).ok,true); assert.equal(p.ack(two.ticket).ok,true);
  assert.equal(p.chargedBytes,0);
});

test('failure retains producer ownership and cannot duplicate after successful move', () => {
  const p=new FlowPortModel({capacity:1,maxBytes:4});
  const a=owned('a',3),b=owned('b',2);
  assert.equal(p.offer(a).ok,true);
  const full=p.offer(b); assert.equal(full.reason,'byte_budget');
  assert.equal(full.value,b); assert.equal(b.owner,'producer');
  assert.throws(()=>p.offer(a),/producer-owned/);
  p.request(1); const [one]=p.takeReady();p.ack(one.ticket);
  assert.equal(p.offer(b).ok,true);
});

test('capacity=0 rendezvous: no queue, only immediate demand admits', () => {
  const p=new FlowPortModel({capacity:0});
  const x=owned('x');
  assert.equal(p.offer(x).reason,'full');assert.equal(x.owner,'producer');
  p.request(1);assert.equal(p.offer(x).ok,true);
  assert.equal(p.queued.length,0);
  const [one]=p.takeReady();p.ack(one.ticket);
});

test('inFlight consumes physical byte budget until explicit acknowledgement', () => {
  const p=new FlowPortModel({capacity:2,maxBytes:4,maxInFlight:1});
  p.request(10);const a=owned('a',3),b=owned('b',2),c=owned('c',1);
  p.offer(a);const [one]=p.takeReady();
  assert.equal(p.offer(b).reason,'byte_budget');
  assert.equal(p.offer(c).ok,true);assert.equal(p.takeReady().length,0);
  assert.equal(p.snapshot().chargedBytes,4);
  p.ack(one.ticket);const [two]=p.takeReady();assert.equal(two.value,c);
  p.ack(two.ticket);assert.equal(p.snapshot().chargedBytes,0);
});

test('finite demand: rejects invalid, overflow and does not silently wrap', () => {
  const p=new FlowPortModel({maxDemand:3});
  for(const n of [0,-1,1.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) assert.throws(()=>p.request(n),/demand/);
  assert.equal(p.request(3).ok,true);
  assert.equal(p.request(1).reason,'demand_overflow');
  assert.equal(p.snapshot().demand,3);
});

test('complete seals admission and drains queued before terminal', () => {
  const p=new FlowPortModel({capacity:2});
  const a=owned('a'),b=owned('b');p.offer(a);p.offer(b);
  assert.equal(p.complete().ok,true);
  assert.equal(p.terminal(),null);
  const c=owned('c');assert.equal(p.offer(c).reason,'closed');assert.equal(c.owner,'producer');
  p.request(2);const delivered=p.takeReady();assert.deepEqual(delivered.map(e=>e.value),[a,b]);
  assert.equal(p.terminal().kind,'complete');assert.equal(p.quiescent,false);
  delivered.forEach(e=>p.ack(e.ticket));assert.equal(p.quiescent,true);
});

test('error/cancel discard queued exactly once but retain in-flight until ack', () => {
  for (const kind of ['error','cancelled']) {
    const p=new FlowPortModel({capacity:2,maxInFlight:1});
    p.request(1);const delivered=owned('delivered'),queued=owned('queued');
    p.offer(delivered);const [one]=p.takeReady();p.offer(queued);
    assert.equal(kind==='error'?p.fail('boom').ok:p.cancel().ok,true);
    assert.equal(p.terminal().kind,kind);
    assert.equal(queued.drops,1);assert.equal(queued.owner,'dropped');
    assert.equal(delivered.owner,'consumer');assert.equal(p.quiescent,false);
    assert.equal(p.cancel().ok,false);assert.equal(queued.drops,1);
    p.ack(one.ticket);assert.equal(p.quiescent,true);
  }
});

test('stale generation and repeated ACK cannot double-refund credit', () => {
  const p=new FlowPortModel({capacity:1});
  p.request(1);p.offer(owned('a'));const [one]=p.takeReady();
  assert.equal(p.complete().ok,true);
  assert.equal(p.restart().reason,'not_quiescent');
  assert.equal(p.ack(one.ticket).ok,true);
  assert.equal(p.ack(one.ticket).reason,'unknown_ticket');
  assert.equal(p.restart().ok,true);
  assert.throws(()=>p.offer(owned('stale'),one.generation),/stale generation/);
  assert.throws(()=>p.request(1,one.generation),/stale generation/);
  assert.equal(p.chargedBytes,0);
});

test('zero leaks under deterministic varied bounded sequences', () => {
  for(let round=1;round<=40;round++) {
    const p=new FlowPortModel({capacity:round%4, maxBytes:7, maxInFlight:2,maxDemand:8});
    let accepted=0;let delivered=0;const values=[];
    for(let i=0;i<20;i++) {
      p.request(1);
      const v=owned(i,1+(i%2));values.push(v);
      const attempt=p.offer(v);
      if(attempt.ok)accepted++;
      for(const event of p.takeReady()) {delivered++;p.ack(event.ticket);}
      assert.ok(p.chargedBytes<=7);
      assert.ok(p.queued.length<=p.capacity);
      assert.ok(p.inFlight.size<=2);
    }
    p.cancel();
    assert.equal(p.chargedBytes,0);
    assert.equal(accepted,delivered+values.filter(v=>v.owner==='dropped').length);
  }
});

test('constructor and value validation fail closed', () => {
  for(const value of [-1,1.2,NaN,Infinity,Number.MAX_SAFE_INTEGER+1]) assert.throws(()=>new FlowPortModel({capacity:value}));
  for(const key of ['maxBytes','maxInFlight','maxDemand']) assert.throws(()=>new FlowPortModel({[key]:0}));
  for(const bytes of [0,-1,1.5,Infinity]) assert.throws(()=>owned('bad',bytes));
  const p=new FlowPortModel();assert.throws(()=>p.offer({data:'forge',bytes:1}),/producer-owned/);
  const v=owned('sealed');
  assert.throws(()=>{v.owner='producer'},/getter/);
  assert.equal(p.offer(v).ok,true);
  assert.throws(()=>{v.owner='producer'},/getter/);
  assert.throws(()=>p.offer(v),/producer-owned/);
  assert.throws(()=>v.admit(),/unauthorized/);
  assert.throws(()=>v.deliver(),/unauthorized/);
  assert.throws(()=>v.drop(),/unauthorized/);
  assert.throws(()=>{v.bytes=999},/read only/);
  assert.equal(v.bytes,1);
});


test('unobserved NEXT cannot refund bytes or expose terminal ahead of delivery', () => {
  const p=new FlowPortModel({capacity:0,maxBytes:1});
  p.request(1); const v=owned('a'); assert.equal(p.offer(v).ok,true);
  assert.equal(p.ack(1).reason,'not_observed');
  assert.equal(p.chargedBytes,1);
  assert.equal(p.complete().ok,true); assert.equal(p.terminal(),null);
  const [next]=p.takeReady(); assert.equal(next.value,v);
  assert.equal(p.terminal().kind,'complete');
  assert.equal(p.ack(next.ticket).ok,true); assert.equal(p.quiescent,true);
});

test('ticket exhaustion reserves a ticket for each accepted queued value', () => {
  const p=new FlowPortModel({capacity:2}); p.nextTicket=Number.MAX_SAFE_INTEGER;
  const a=owned('a'), b=owned('b'); assert.equal(p.offer(a).ok,true);
  assert.equal(p.offer(b).reason,'ticket_exhausted'); assert.equal(b.owner,'producer');
  p.request(1); const [next]=p.takeReady(); assert.equal(next.ticket,Number.MAX_SAFE_INTEGER);
  assert.equal(p.ack(next.ticket).ok,true); assert.equal(p.chargedBytes,0);
});
