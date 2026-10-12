from .database import connect, audit
from .validation_engine import validate_project

def load_demo():
    pid='demo-autoarch'
    with connect() as con:
        if con.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():
            return pid
        con.execute('INSERT INTO projects(id,name,description,synthetic) VALUES(?,?,?,1)',(pid,'Synthetic EV Thermal & Display Architecture','Synthetic demonstration fixture; not production architecture.'))
        comps=[('VehicleSpeedProvider','Provides vehicle speed data.'),('ThermalManager','Coordinates thermal control.'),('BatteryMonitor','Monitors battery status.'),('DriverDisplay','Presents driver information.'),('DiagnosticGateway','Routes diagnostic requests.')]
        comps_new=comps+[('DisplayVehicleInfoAdapter','Adapts vehicle signals for display consumers.')]
        for rev, rows in [('1.0',comps),('1.1',comps_new)]:
            for name,desc in rows: con.execute('INSERT INTO components(project_id,revision,entity_id,name,description,page,evidence,confidence) VALUES(?,?,?,?,?,?,?,?)',(pid,rev,name,name,desc,1,f'Synthetic fixture: {desc}','synthetic'))
        interfaces=[('VehicleSpeedService','VehicleSpeedProvider','["DriverDisplay"]','vehicle_speed'),('BatteryStatusService','BatteryMonitor','["ThermalManager","DriverDisplay"]','battery_status'),('WarningDisplayService','ThermalManager','["DriverDisplay"]','warning'),('DiagnosticRequestService','DiagnosticGateway','["MissingDiagnosticClient"]','diagnostic_request')]
        for rev, rows in [('1.0',interfaces),('1.1',[('VehicleSpeedService','VehicleSpeedProvider','["DisplayVehicleInfoAdapter"]','vehicle_speed'),('DisplayVehicleInfoService','DisplayVehicleInfoAdapter','["DriverDisplay"]','display_vehicle_info'),*interfaces[1:3],interfaces[3]])]:
            for name,provider,consumers,data in rows: con.execute('INSERT INTO interfaces(project_id,revision,entity_id,name,provider,consumers,data,page,evidence) VALUES(?,?,?,?,?,?,?,?,?)',(pid,rev,name,name,provider,consumers,data,2,f'Synthetic fixture interface {name}: provider {provider}, consumers {consumers}.'))
        deps1=[('DriverDisplay','VehicleSpeedProvider'),('ThermalManager','BatteryMonitor'),('DriverDisplay','DiagnosticGateway')]
        deps2=deps1+[('DriverDisplay','DisplayVehicleInfoAdapter')]
        for rev, rows in [('1.0',deps1),('1.1',deps2)]:
            for a,b in rows: con.execute('INSERT INTO dependencies(project_id,revision,source,target,reason,page,evidence) VALUES(?,?,?,?,?,?,?)',(pid,rev,a,b,'Synthetic demonstration dependency',2,'Synthetic fixture relationship.'))
    audit(pid,'demo_loaded','Loaded synthetic baseline revisions 1.0 and 1.1')
    validate_project(pid)
    return pid
