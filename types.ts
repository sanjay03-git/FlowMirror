export type Congestion = 'low' | 'medium' | 'high'
export interface Road { id:string; from_node:string; to_node:string; current_speed_kmph:number; speed_limit_kmph:number; congestion_level:Congestion; blocked:boolean }
export interface Intersection { id:string; name:string; latitude:number; longitude:number }
export interface Vehicle { id:string; current_road_id:string; speed_kmph:number; latitude:number; longitude:number; status:string }
export interface Incident { id:string; road_id:string; type:string; severity:string; message:string; created_at:string; affected_lanes?:number; estimated_clearance_minutes?:number; response_status:string }
export interface Alert { id:string; audience:'traveller'|'police'|'traffic_control'; priority:'info'|'warning'|'critical'; title:string; message:string; road_id:string; created_at:string; acknowledged:boolean }
export interface Signal { id:string; intersection_id:string; mode:'adaptive'|'emergency'; active_road_id:string; phase_label:string; green_seconds:number; reason:string }
export interface Camera { id?:string; name?:string; intersection_id?:string; corridor?:string; state:string; vehicle_count:number; average_speed_kmph:number; congestion:string; stopped_vehicle_risk:boolean; message:string; fps?:number; detections?:Array<{id:string;class:string;confidence:number;lane:number}> }
export interface Responder { id:string; incident_id:string; unit_type:'police'|'ambulance'|'fire'; origin:string; destination_road_id:string; eta_minutes:number; progress_percent:number; status:string }
export interface RouteStrategy { strategy:string; label:string; nodes:string[]; roads:string[]; eta_minutes:number; distance_km:number; delay_minutes:number; traffic_score:number; average_speed_kmph:number; confidence:number }
export interface TwinState { intersections:Intersection[]; roads:Road[]; vehicles:Vehicle[]; incidents:Incident[]; alerts:Alert[]; signals:Signal[]; responders?:Responder[]; camera?:Camera; cameras?:Camera[]; summary:{active_vehicles:number;high_congestion_roads:number;active_incidents:number;average_network_speed_kmph:number} }
