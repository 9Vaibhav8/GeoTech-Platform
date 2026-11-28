"""Optional CE 402 example. Source: assignment pp. 1–6 (hypothetical data).
No data in this module is used unless the user explicitly loads the demo.
Raw observations are separated from illustrative engineering assumptions.
"""
from copy import deepcopy
from math import log10, degrees, atan
from .constants import DEFAULT_LAYER
from .spt_corrections import correct_spt_records, apply_spt_to_layers, fit_mohr_coulomb
from .bearing_capacity import effective_overburden_pressure

# top, bottom, symbol, moist, saturated (None = not supplied in assignment)
BOREHOLES = {
 'BH-1': dict(rl=100.00, measured=2.6, design=1.0, lowest=3.6, layers=[(0,.6,'Fill',16.5,None),(.6,3.4,'SM',18,20),(3.4,5.8,'SP',19,20.4),(5.8,10.6,'CI',None,18.6),(10.6,15,'GW',None,21.5)]),
 'BH-2': dict(rl=100.20, measured=3.2, design=1.7, lowest=4.2, layers=[(0,.5,'Fill',16.5,None),(.5,3.8,'SM',18.2,20),(3.8,7.6,'SP',19.3,20.6),(7.6,9.6,'CI',None,18.7),(9.6,15,'GW',None,21.5)]),
 'BH-3': dict(rl=99.70, measured=1.9, design=.6, lowest=3.0, layers=[(0,.9,'Fill',16,None),(.9,2.6,'SM',17.5,19.5),(2.6,4.4,'SP',18.6,20),(4.4,11.2,'CI',None,18.5),(11.2,15,'GW',None,21.5)])}
# depth, test class, raw N, refusal penetration in mm, excluded reason
FINE='Fine/Silty Sand'; SAND='Coarse/Medium Sand'; CLAY='Clay'; GRAVEL='Cobble/Boulder Gravel'
SPT = {
 'BH-1': [(1.5,FINE,13,None,''),(3,FINE,16,None,''),(4.5,SAND,24,None,''),(6,CLAY,6,None,''),(7.5,CLAY,5,None,''),(9,GRAVEL,22,None,'Cobble strike; gravel only recovered'),(10.5,CLAY,8,None,''),(12,GRAVEL,None,60,''),(13.5,GRAVEL,None,45,'')],
 'BH-2': [(1.5,FINE,14,None,''),(3,FINE,17,None,''),(4.5,SAND,26,None,''),(6,SAND,31,None,''),(7.5,SAND,34,None,''),(9,CLAY,9,None,''),(10.5,GRAVEL,None,70,''),(12,GRAVEL,None,50,'')],
 'BH-3': [(1.5,FINE,6,None,''),(3,SAND,14,None,''),(4.5,CLAY,4,None,''),(6,CLAY,4,None,''),(7.5,CLAY,5,None,''),(9,CLAY,6,None,''),(10.5,CLAY,8,None,''),(12,GRAVEL,None,55,''),(13.5,GRAVEL,None,40,'')]}
DIRECT_SHEAR = {'SM unsoaked (BH-1 DS-1)': [37,67,97.2], 'SM soaked (BH-1 DS-1)': [29.8,58.9,87.5], 'SP soaked (BH-1 SPT-3)': [34.9,68.3,103.4]}
UU = {'UDS-1 (BH-1)': [57.2,55.8,58.1], 'UDS-2 (BH-1)': [71,73.4,72.2]}
# pressure kgf/cm², void ratio, stage, cv cm²/s (as reported)
OEDOMETER = [(0.10,.914,'Loading',None),(.25,.897,'Loading',1.2e-3),(.5,.882,'Loading',1.1e-3),(1,.853,'Loading',8.9e-4),(2,.779,'Loading',6.3e-4),(4,.692,'Loading',5e-4),(8,.603,'Loading',4.4e-4),(2,.626,'Unloading',None),(.5,.649,'Unloading',None)]
SERVICE_LOADS = {'Corner':650.,'Edge':1000.,'Interior':1450.}
ZONES={'BH-1':(3,5),'BH-2':(1,2),'BH-3':(6,7)}
# Missing C4 load/moment in supplied table: demonstration only, not assignment data.
TRIAL_LOADS={**SERVICE_LOADS,'Special':1450.}
TRIAL_WIDTHS={'Corner':2.,'Edge':2.5,'Interior':3.,'Special':3.}
ASSUMPTIONS = [
 'Fill saturated unit weight = 19 kN/m³; missing clay/gravel moist weight = saturated weight (illustrative only).',
 'BH-1 soaked shear tests fitted by OLS; BH-2/3 sand strengths transferred from BH-1 only for this demo.',
 'Fill φ′=25°, gravel φ′=38°, clay drained c′=5 kPa and φ′=20° are assumed; clay cu from mean UDS-1/2 for BH-1, 35/20 kPa assumed for BH-2/3.',
 'BH-1 consolidation: Cc from 2–8 kgf/cm² loading, Cr from 2–0.5 unloading, e₀=0.918, trial Pc=1 kgf/cm² (not a measured Pc), cv at 2 kgf/cm² converted to m²/s. Transferred Cc/Cr/Pc/cv to BH-2/3 for demo; e₀ estimated from saturated wGs (33%/35%, assumed Gs=2.70).',
 'Es = 8 MPa for fill and 60 MPa for gravel, assumed. Other granular stiffness uses the existing corrected-SPT correlation; verify its applicability.',
 'Trial square sizes 2/2.5/3 m for corner/edge/interior; C4 assumed concentric with 1450 kN and 3 m square ONLY to show the grid. C4 load and moment are not supplied; replace before design.',
 'For demonstration the scaled column service loads are treated as effective gross contact loads, neglecting foundation/backfill and pore-pressure corrections. P4 net pressure subtracts effective surcharge using this same assumption.',
 'SPT sand grain-size classes are interpreted from the logs; drainage, 50-year design horizon and category/soil limit choices are illustrative. Confirm for the actual site.'
]

def spt_records(name):
    return [dict(depth_m=z,soil_class=soil,N_field=n,is_refusal=penetration is not None,excluded=bool(note),estimated_depth=False,note=f'50 blows / {penetration} mm; reported N > 100' if penetration else note) for z,soil,n,penetration,note in SPT[name]]

def make_profiles():
    c_sm,phi_sm,_=fit_mohr_coulomb([50,100,150],DIRECT_SHEAR['SM soaked (BH-1 DS-1)'])
    if c_sm < 0: # explicit constrained example fit; raw P2 OLS is unchanged
        c_sm=0.; phi_sm=degrees(atan(sum(x*y for x,y in zip([50,100,150],DIRECT_SHEAR['SM soaked (BH-1 DS-1)']))/35000.))
    c_sp,phi_sp,_=fit_mohr_coulomb([50,100,150],DIRECT_SHEAR['SP soaked (BH-1 SPT-3)'])
    # SP OLS may also be slightly negative; constrain only if needed.
    if c_sp < 0:
        c_sp=0.; phi_sp=degrees(atan(sum(x*y for x,y in zip([50,100,150],DIRECT_SHEAR['SP soaked (BH-1 SPT-3)']))/35000.))
    cc=(.779-.603)/log10(8/2); cr=(.649-.626)/log10(2/.5)
    profiles={}
    for name,raw in BOREHOLES.items():
        layers=[]
        for top,bot,symbol,moist,sat in raw['layers']:
            layer={**DEFAULT_LAYER,'depth_top':top,'depth_bot':bot,'symbol':symbol,'name':{'Fill':'Fill','SM':'Silty sand','SP':'Poorly graded sand','CI':'Silty clay','GW':'Sandy gravel'}[symbol], 'gamma_moist':sat if moist is None else moist,'gamma_sat':19. if sat is None else sat}
            if symbol=='SM': layer.update(c_prime=c_sm,phi_prime=phi_sm)
            elif symbol=='SP': layer.update(c_prime=c_sp,phi_prime=phi_sp)
            elif symbol=='Fill': layer.update(phi_prime=25.,Es_kPa=8000.)
            elif symbol=='GW': layer.update(phi_prime=38.,Es_kPa=60000.,N_refusal=True,N_refusal_note='See depth-specific SPT records')
            else:
                layer.update(is_clay=True,is_undrained=True,c_prime=5.,phi_prime=20.,cu=sum(sum(v) for v in UU.values())/12 if name=='BH-1' else (35. if name=='BH-2' else 20.),Cc=cc,Cr=cr,e0={'BH-1':.918,'BH-2':.33*2.7,'BH-3':.35*2.7}[name],Pc_kPa=98.0665,cv_m2s=6.3e-8)
            # Raw test counts remain depth-specific, not invented mid-depth counts.
            layers.append(layer)
        results=correct_spt_records(spt_records(name),layers,raw['measured'])
        apply_spt_to_layers(layers,results)
        profiles[name]=dict(layers=layers,wt_design_bgl=raw['design'],wt_measured_bgl=raw['measured'],ground_rl=raw['rl'])
    return profiles

def clear_analysis(state):
    """Explicit project reset; preserve unrelated application keys."""
    exact={'layers','borehole_name','ground_rl','wt_measured_bgl','wt_design_bgl','foundation_depth','boreholes','spt_records','spt_results','ds_data','uu_data','mc_fit','cu_result','profile_valid','profile_errors','superpos_areas','demo_project','demo_assumptions'}
    prefixes=('p1_','p2_','p3_','p4_','p5_','sidebar_','btn_','sp_','mc_','cu_','ds_','uu_')
    for k in list(state.keys()):
        if k in exact or str(k).startswith(prefixes): del state[k]

def load_demo(state,name='BH-1',group=0,shear='SM soaked (BH-1 DS-1)',uu='UDS-1 (BH-1)'):
    if int(group)!=group or group<0: raise ValueError('Group must be a nonnegative integer.')
    profiles=make_profiles(); p=profiles[name]; factor=1+group/100
    clear_analysis(state)
    state.update(layers=deepcopy(p['layers']),borehole_name=name,ground_rl=p['ground_rl'],wt_measured_bgl=p['wt_measured_bgl'],wt_design_bgl=p['wt_design_bgl'],foundation_depth=1.5,boreholes=deepcopy(profiles),spt_records=spt_records(name),ds_data=[dict(sigma_n=x,tau=y) for x,y in zip([50,100,150],DIRECT_SHEAR[shear])],uu_data=[dict(sigma3=x,deviator=y) for x,y in zip([50,100,150],UU[uu])])
    surcharge,_=effective_overburden_pressure(p['layers'],1.5,p['wt_design_bgl'])
    state['demo_project']=dict(name='CE 402 hostel example',group=int(group),factor=factor,active=name,loads=deepcopy(TRIAL_LOADS),widths=deepcopy(TRIAL_WIDTHS),zones=deepcopy(ZONES),p4_net_load=SERVICE_LOADS['Edge']*factor-surcharge*2.5**2,shear=shear,uu=uu)
    state['demo_assumptions']=list(ASSUMPTIONS)

def reset_generic(state):
    clear_analysis(state)
    # Blank soil profile, not a new set of invented measurements.
    state.update(layers=[],borehole_name='New site',ground_rl=0.,wt_measured_bgl=0.,wt_design_bgl=0.,foundation_depth=1.5)

def demo_notice(st):
    if st.session_state.get('demo_project'):
        st.warning('Illustrative CE 402 demo active — source observations plus explicit assumptions. Not a verified foundation design. See Home for the assumptions and reset controls.')
