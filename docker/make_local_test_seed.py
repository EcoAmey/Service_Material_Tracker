"""Generates docker/local-test-seed.sql: dummy tickets + dispatched items at
every stage of the flow, for the LOCAL test database only (never RDS).

    python docker/make_local_test_seed.py
    mysql -u<root user> -p < docker/local-test-seed.sql      # against a throwaway local MySQL

It expects the schemas `fault_tracker` (this app's tables) and `clappia`
(the ez_service stand-in), as created by the local-db compose profile -- it
will not do anything against the real RDS databases, which have other names.

The SQL is re-runnable: it first deletes anything a previous run created
(service IDs starting with 'T26'), then re-inserts it.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django  # noqa: E402

django.setup()
from tracker import forms as F  # noqa: E402

first = lambda choices: choices[0][0]
q = lambda v: 'NULL' if v is None else "'" + str(v).replace("'", "''") + "'"

# user ids in the dumped users table
WAREHOUSE, REGWH, REGWH2, DESK, ELEC = 1, 5, 8, 9, 10
ENGINEERS = {  # id: (name, email)
    2: ('Ajay More', 'ajaymore92108038@gmail.com'),
    3: ('Akash Narwade', 'akashnarwade009@gmail.com'),
    4: ('Ashok Pawar', 'ashokpawar50825@gmail.com'),
    6: ('Hari_Hisar_HR', 'hs9005640@gmail.com'),
    11: ('Satish Kumar', 'satish.kumar0391@gmail.com'),
    12: ('Surendra_Moradabad_UP', 'smaurya01995@gmail.com'),
    14: ('Nilesh_Beed_MH2', 'nileshecozen@gmail.com'),
    15: ('Ashok_Nagaur_RJ', 'rashoksingh939@gmail.com'),
    16: ('Shekhar_Dhule_MH2', 'sedhule01@gmail.com'),
    17: ('Anup_Shahjahanpur_UP.', 'anupkumar174017@gmail.com'),
    18: ('Bhushan_SM_MH1', 'bhushan.maske@ecozensolutions.com'),
}
LOC = {'rsc2': 2, 'rsc3': 3, 'wh': 4}              # dispatch locations (Regional_warehouse1, EZ_Hisar_Store., Pune Warehouse)
LOC_USER = {'rsc2': REGWH, 'rsc3': REGWH2, 'wh': WAREHOUSE}
PARTNERS = [5, 3, 2, 4]
BY_HAND = 8

# slot, part_type, label/name, columns on the Clappia ticket
SLOTS = {'pc': ('power_card', 'Power Card'), 'cc': ('control_card', 'Control Card')}
MATERIALS = {'sm': 'Submersible Motor', 'sp': 'Submersible Pump', 'sf': 'Surface Pump',
             'cable': 'Sub Cable', 'mc4': 'MC4 Connector (IP65 Controller Side)'}

# stage -> (final status, ordered status events after 'dispatched', where it is at, kind)
#   where: 'dest' = still at the original destination, 'fwd' = forwarded to Pune warehouse
STAGES = {
    'pending': None,
    'incoming': ('dispatched', [], 'dest'),
    'received_card': ('dispatched', [], 'dest'),
    'received_card_fix': ('dispatched', [], 'dest'),
    'received_motor': ('dispatched', [], 'dest'),
    'fwd': ('dispatched_to_warehouse', ['dispatched_to_warehouse'], 'fwd'),
    'fwd_motor': ('dispatched_to_warehouse', ['dispatched_to_warehouse'], 'fwd'),
    'sd': ('with_service_desk', ['with_service_desk'], 'dest'),
    'elec': ('with_electronics', ['with_service_desk', 'with_electronics'], 'dest'),
    'elec_done': ('electronics_completed', ['with_service_desk', 'with_electronics', 'electronics_completed'], 'dest'),
    'elec_done_scrap': ('electronics_completed', ['with_service_desk', 'with_electronics', 'electronics_completed'], 'dest'),
    'back': ('repaired_by_electronics', ['with_service_desk', 'with_electronics', 'electronics_completed', 'repaired_by_electronics'], 'dest'),
    'stock': ('added_to_stock', ['with_service_desk', 'with_electronics', 'electronics_completed', 'repaired_by_electronics', 'added_to_stock'], 'dest'),
    'pcard_pending': ('pending_oem_scrap', ['pending_oem_scrap'], 'dest'),
    'pcard_oem': ('dispatched_to_oem', ['pending_oem_scrap', 'dispatched_to_oem'], 'dest'),
    'pcard_scrap': ('scrapped', ['pending_oem_scrap', 'scrapped'], 'dest'),
    'motor_oem': ('dispatched_to_oem', ['dispatched_to_oem'], 'dest'),
    'motor_scrap': ('scrapped', ['scrapped'], 'dest'),
    'motor_repaired': ('repaired', ['repaired'], 'dest'),
    'tested_ok': ('tested_ok', ['tested_ok'], 'dest'),
}

# (ticket, engineer id, days ago dispatched/registered, [(slot, serial, problem, stage, destination)])
TICKETS = [
    ('T260001', 2, 3, [('pc', 'PC-A1001', 'Display blank', 'pending', None), ('cc', 'CC-A1001', 'No power', 'pending', None), ('sm', 'SM-1001', 'Winding burnt', 'pending', None)]),
    ('T260002', 3, 5, [('sp', 'SP-2001', 'Impeller damage', 'incoming', 'rsc2'), ('sf', 'SF-2001', 'Seal leak', 'incoming', 'rsc2'), ('pc', 'PC-2001', 'IGBT short', 'incoming', 'rsc2')]),
    ('T260003', 4, 7, [('sm', 'SM-3001', 'Rotor spline damage', 'received_motor', 'rsc2'), ('sp', 'SP-3001', 'Coupling damage', 'received_motor', 'rsc2'), ('cc', 'CC-3001', 'Comm fault', 'received_card', 'rsc2')]),
    ('T260004', 6, 9, [('pc', 'PC-4001', 'Fan failure', 'received_card_fix', 'rsc3'), ('sp', 'SP-4001', 'Shaft broken', 'fwd_motor', 'rsc3'), ('sf', 'SF-4001', 'Bearing noise', 'fwd_motor', 'rsc3')]),
    ('T260005', 11, 12, [('pc', 'PC-5001', 'Overheating', 'incoming', 'wh'), ('cc', 'CC-5001', 'Display fault', 'sd', 'wh'), ('sm', 'SM-5001', 'Winding burnt', 'incoming', 'wh'), ('sf', 'SF-5001', 'Low discharge', 'incoming', 'wh')]),
    ('T260006', 12, 15, [('pc', 'PC-6001', 'No output', 'elec', 'wh'), ('cc', 'CC-6001', 'Reset loop', 'elec_done', 'wh'), ('sp', 'SP-6001', 'Stage damage', 'received_motor', 'wh')]),
    ('T260007', 14, 20, [('pc', 'PC-7001', 'Burnt track', 'elec_done_scrap', 'wh'), ('cc', 'CC-7001', 'Water ingress', 'back', 'wh'), ('sm', 'SM-7001', 'Rotor stuck', 'motor_oem', 'wh')]),
    ('T260008', 15, 25, [('pc', 'PC-8001', 'Surge damage', 'stock', 'wh'), ('cc', 'P-CC8001', 'Dead board', 'pcard_pending', 'wh'), ('sp', 'SP-8001', 'Cracked housing', 'motor_scrap', 'wh')]),
    ('T260009', 16, 30, [('pc', 'P-PC9001', 'Dead board', 'pcard_oem', 'wh'), ('cc', 'P-CC9001', 'Burnt', 'pcard_scrap', 'wh'), ('sf', 'SF-9001', 'Seal leak', 'motor_repaired', 'wh')]),
    ('T260010', 17, 35, [('sm', 'SM-A001', 'Winding burnt', 'motor_oem', 'wh'), ('sp', 'SP-A001', 'Impeller damage', 'motor_oem', 'wh'), ('pc', 'PC-A001', 'IGBT short', 'stock', 'wh')]),
    ('T260011', 18, 45, [('cc', 'CC-B001', 'Comm fault', 'stock', 'wh'), ('pc', 'PC-B001', 'Overheating', 'sd', 'wh'), ('sf', 'SF-B001', 'Low discharge', 'motor_repaired', 'wh'), ('cable', 'SC-B001', 'Cut cable', 'pending', None)]),
    ('T260012', 2, 55, [('pc', 'PC-C001', 'No output', 'stock', 'wh'), ('sm', 'SM-C001', 'Rotor stuck', 'motor_scrap', 'wh'), ('mc4', 'MC-C001', 'Burnt connector', 'pending', None)]),
    ('T260013', 3, 2, [('sm', 'SM-D001', 'Winding burnt', 'pending', None), ('sp', 'SP-D001', 'Impeller damage', 'pending', None), ('sf', 'SF-D001', 'Seal leak', 'pending', None)]),
    ('T260014', 11, 65, [('pc', 'PC-E001', 'Legacy tested ok', 'tested_ok', 'rsc2'), ('cc', 'CC-E001', 'Archived sample', 'stock', 'wh')]),
]
ARCHIVED_SERIALS = {'CC-E001'}

out = ['-- LOCAL TEST SEED (generated by make_local_test_seed.py). Not for RDS.', '']
out += [
    "USE fault_tracker;",
    "DELETE e FROM fault_tracker.tracker_dispatchitemstatusevent e JOIN fault_tracker.tracker_dispatchitem i ON i.id = e.item_id WHERE i.service_id LIKE 'T26%';",
    "DELETE FROM fault_tracker.tracker_dispatchitem WHERE service_id LIKE 'T26%';",
    "DELETE FROM fault_tracker.tracker_dispatch WHERE remarks = 'LOCAL TEST SEED';",
    "DELETE FROM clappia.ez_service WHERE service_id LIKE 'T26%';", '',
]

ago = lambda days, hours=0: f'NOW() - INTERVAL {days * 24 - hours} HOUR'
cap = '5 HP'
oem_sub, oem_surf = F.SUBMERSIBLE_PUMP_OEM_CHOICES[0][0], F.MOTOR_SURFACE_OEM_CHOICES[0][0]
head, inch = F.MOTOR_HEAD_SIZE_CHOICES[1][0], F.MOTOR_INCH_SIZE_CHOICES[1][0]
dmg, comp = first(F.PHYSICAL_VISUAL_DAMAGE_CHOICES), first(F.COMPONENT_STATUS_CHOICES)
pef, sdb = first(F.POWER_ELECTRICAL_FAULT_CHOICES), first(F.SYSTEM_DISPLAY_BEHAVIOR_CHOICES)
fcat, subcat = first(F.FAILURE_CATEGORY_CHOICES), first(F.SUB_CATEGORY_CHOICES)

dispatch_vars = {}
n_dispatch = 0


def dispatch(ticket, key, user, days, dest_id, partner, n, forwarded=False):
    global n_dispatch
    if (ticket, key) in dispatch_vars:
        return dispatch_vars[(ticket, key)]
    n_dispatch += 1
    var = f'@d{n_dispatch}'
    by_hand = partner == BY_HAND
    out.append(
        "INSERT INTO tracker_dispatch (dispatched_by_id, pickup_number, lr_number, delivery_challan_number, delivery_partner_id, destination_id, remarks, dispatched_at) VALUES "
        f"({user}, {q('' if by_hand else 'PU-' + ticket[-4:] + key[:1])}, {q('' if by_hand else 'LR-' + ticket[-4:] + key[:1])}, "
        f"{q('' if by_hand else 'DC-' + ticket[-4:] + key[:1])}, {partner}, {dest_id}, 'LOCAL TEST SEED', {ago(days, 6 if forwarded else 0)});"
    )
    out.append(f'SET {var} = LAST_INSERT_ID();')
    dispatch_vars[(ticket, key)] = var
    return var


for ti, (ticket, eng, days, parts) in enumerate(TICKETS):
    ename, email = ENGINEERS[eng]
    cols = {'faulty_power_card_no': None, 'faulty_control_card_no': None, 'controller_display_fault': None}
    mat = 0
    for slot, serial, problem, stage, dest in parts:
        if slot == 'pc':
            cols['faulty_power_card_no'] = serial; cols['controller_display_fault'] = problem
        elif slot == 'cc':
            cols['faulty_control_card_no'] = serial; cols['controller_display_fault'] = cols['controller_display_fault'] or problem
        else:
            mat += 1
            cols[f'component_{mat}'] = MATERIALS[slot]; cols[f'faulty_part_no_{mat}'] = serial; cols[f'problem_{mat}'] = problem
    names = ', '.join(cols)
    out.append(
        f"INSERT INTO clappia.ez_service (submission_id, complaint_reg_date, service_id, machine_no, farmer_name, village, taluka, district, state, si_name, engineer_name, engineer_mail, status, {names}) VALUES "
        f"('SEED{ticket}', CURDATE() - INTERVAL {days + 2} DAY, '{ticket}', 'EZMCSEED{ti:04d}', 'Farmer {ti + 1}', 'Village {ti + 1}', 'Taluka', 'District', 'Maharashtra', 'ECOZEN', "
        f"{q(ename)}, {q(email)}, 'Completed', {', '.join(q(v) for v in cols.values())});"
    )

    mat = 0
    for slot, serial, problem, stage, dest in parts:
        if slot in SLOTS:
            part_type, material = SLOTS[slot]
        else:
            part_type, material = 'material', MATERIALS[slot]
        if STAGES[stage] is None:
            continue
        final, steps, where = STAGES[stage]
        partner = BY_HAND if ticket == 'T260006' else PARTNERS[ti % len(PARTNERS)]
        d_var = dispatch(ticket, dest, eng, days, LOC[dest], partner, ti)
        fwd_var = 'NULL'
        if where == 'fwd':
            fwd_var = dispatch(ticket, 'fwd', LOC_USER[dest], days, LOC['wh'], PARTNERS[(ti + 1) % len(PARTNERS)], ti, forwarded=True)
        at_main = dest == 'wh' or where == 'fwd'
        mover = LOC_USER['wh'] if at_main else LOC_USER[dest]
        is_motor = part_type == 'material' and slot in ('sm', 'sp', 'sf')
        is_card = part_type != 'material'

        f = {  # DispatchItem columns
            'dispatch_id': d_var, 'service_id': q(ticket), 'part_type': q(part_type), 'faulty_serial': q(serial),
            'material_name': q(material), 'problem': q(problem), 'controller_serial': q(f'EZMCSEED{ti:04d}'),
            'si_details': q('ECOZEN'), 'farmer_name': q(f'Farmer {ti + 1}'), 'location': q('Village ' + str(ti + 1)),
            'service_person_name': q(ename), 'replacement_date': f'CURDATE() - INTERVAL {days + 2} DAY',
            'created_at': ago(days), 'status': q(final), 'status_remarks': q(''), 'forward_dispatch_id': fwd_var,
            'is_archived': 1 if serial in ARCHIVED_SERIALS else 0,
        }
        if serial in ARCHIVED_SERIALS:
            f['archived_at'] = 'NOW()'
        if stage != 'incoming':
            f['status_updated_by_id'] = mover
            f['status_updated_at'] = ago(days, len(steps) + 2)
        if is_card and stage != 'incoming':
            f.update(received_date=f'CURDATE() - INTERVAL {max(days - 1, 0)} DAY', received_serial_matches=1,
                     warehouse_reservation_no=q(f'RES-{ticket[-4:]}'))
            if stage == 'received_card_fix':
                f.update(received_serial_matches=0, received_serial_no=q(serial + '-FIX'), status_remarks=q('Serial differs from ticket'))
        if is_motor and stage != 'incoming':
            f.update(received_date=f'CURDATE() - INTERVAL {max(days - 1, 0)} DAY', motor_capacity=q(cap),
                     motor_oem_name=q(oem_sub if slot in ('sm', 'sp') else oem_surf))
            if slot != 'sm':
                f.update(motor_head_size=q(head), motor_inch_size=q(inch))
        if 'received_date' in f:
            f['destination_received_date'] = f['received_date']
        if stage in ('motor_oem', 'motor_scrap'):
            f.update(oem_inward_reservation_no=q(f'IN-{ticket[-4:]}'), oem_outward_reservation_no=q(f'OUT-{ticket[-4:]}'))
        if stage == 'pcard_oem':
            f.update(oem_dispatch_lr_no=q('OEM-LR-' + ticket[-4:]), oem_dispatch_challan_no=q('OEM-DC-' + ticket[-4:]),
                     oem_outward_reservation_no=q('OUT-' + ticket[-4:]))
        if stage == 'pcard_scrap':
            f.update(scrap_condition=q('burn'), oem_outward_reservation_no=q('OUT-' + ticket[-4:]))
        if stage in ('elec', 'elec_done', 'elec_done_scrap', 'back', 'stock'):
            f.update(inspection_problem=q(problem), inspection_visual_done=1, inspection_mtr_test_passed=1,
                     inspection_cold_test_passed=1, inspection_wiring_repaired=0, inspection_reservation_no=q('INSP-' + ticket[-4:]))
        if stage in ('elec_done', 'elec_done_scrap', 'back', 'stock'):
            remark = 'scrapped' if stage == 'elec_done_scrap' else 'repaired_ok'
            f.update(electronics_engineer_name=q('Electronics Eng'), electronics_physical_visual_damage=q(dmg),
                     electronics_component_status=q(comp), electronics_power_electrical_faults=q(pef),
                     electronics_system_display_behavior=q(sdb), electronics_pcb_type=q('NA'), electronics_pcb_issue=q('NA'),
                     electronics_failure_category=q(fcat), electronics_sub_category=q(subcat), electronics_igbt_pin_status=q('NA'),
                     electronics_component_change=q('Capacitor C12'), electronics_test_machine_info=q('Bench 3'),
                     electronics_tested_date='CURDATE()', electronics_final_remark=q(remark))
        if stage in ('back', 'stock'):
            f['electronics_outward_reservation_no'] = q('EOUT-' + ticket[-4:])
        if stage == 'stock':
            f['stock_outward_reservation_no'] = q('STK-' + ticket[-4:])

        out.append(f"INSERT INTO tracker_dispatchitem ({', '.join(f)}) VALUES ({', '.join(str(v) for v in f.values())});")
        out.append('SET @i = LAST_INSERT_ID();')
        who = {'dispatched': eng, 'dispatched_to_warehouse': LOC_USER[dest], 'with_service_desk': WAREHOUSE,
               'pending_oem_scrap': WAREHOUSE, 'with_electronics': DESK, 'electronics_completed': ELEC,
               'repaired_by_electronics': ELEC}
        events = [('dispatched', eng)] + [(s, who.get(s, WAREHOUSE)) for s in steps]
        vals = ', '.join(
            f"(@i, '{s}', '', {u}, {ago(days, k * 3)})" for k, (s, u) in enumerate(events)
        )
        out.append(f'INSERT INTO tracker_dispatchitemstatusevent (item_id, status, remarks, changed_by_id, changed_at) VALUES {vals};')
    out.append('')

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local-test-seed.sql')
open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('wrote', path, '-', n_dispatch, 'dispatches')
