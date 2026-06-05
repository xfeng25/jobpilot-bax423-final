// ─── Personas (per BAX-423 assignment spec) ──────────────────────────────────
const PERSONAS = {
  aisha:{
    name:"Aisha Patel",email:"aisha.patel@example.com",phone:"415-555-0133",
    linkedin:"linkedin.com/in/aishapatel",currentLocation:"San Francisco, CA",workAuth:"U.S. Citizen",
    education:[{school:"UC Davis",degree:"MSBA",major:"Business Analytics",start:"2024-09",end:"2026-06"}],
    experience:[{company:"BrightRetail",title:"Data Analyst",start:"2023-05",end:"Present",current:true,
      description:"Used Python, SQL, pandas, and scikit-learn for retail forecasting and customer segmentation. Basic PyTorch exposure through coursework."}],
    skills:["Python","SQL","pandas","scikit-learn","basic PyTorch"],
    projects:[{name:"Retail Forecasting Model",description:"Built demand forecasting models using Python and ML.",tech:"Python, scikit-learn"}],
    certifications:[],
    cRole:"ML Engineer, Applied Scientist, Data Scientist",
    cSkills:"Python, SQL, pandas, scikit-learn, basic PyTorch",
    cLocation:"Remote, Bay Area",cPreferences:"ML-focused",
    cSalary:140000,cEmpType:"Full-time",cVisa:"",
    dealbreakers:["No Senior Roles","No Staff Roles","No Defense Companies","No 5+ Years ML Required"]
  },
  marcus:{
    name:"Marcus Chen",email:"marcus.chen@ucdavis.edu",phone:"530-555-0187",
    linkedin:"linkedin.com/in/marcuschen-msba",currentLocation:"Davis, CA",workAuth:"U.S. Citizen",
    education:[{school:"UC Davis",degree:"MSBA",major:"Business Analytics",start:"2024-09",end:"2026-06"}],
    experience:[
      {company:"Sutter Health",title:"Analytics Intern",start:"2025-06",end:"2025-09",current:false,
        description:"Built Tableau dashboards and SQL models for clinic operations."},
      {company:"Aggie Insights Lab",title:"Data Analytics Intern",start:"2025-01",end:"2025-05",current:false,
        description:"Analyzed support tickets using Python and NLP workflows."}
    ],
    skills:["Python","R","SQL","Tableau","PySpark","basic NLP"],
    projects:[{name:"Healthcare Access Dashboard",description:"Built dashboard for clinic access metrics.",tech:"SQL, Tableau"}],
    certifications:[{name:"Tableau Desktop Specialist",issuer:"Tableau",date:"2025"}],
    cRole:"Data Analyst, BI Analyst, Junior Data Scientist, Analytics Engineer",
    cSkills:"Python, R, SQL, Tableau, PySpark, basic NLP",
    cLocation:"Any US location",cPreferences:"tech, healthcare",
    cSalary:80000,cEmpType:"Full-time",cVisa:"",
    dealbreakers:["No Contract Roles","No Unpaid Roles","No 3+ Years Required"]
  },
  priya:{
    name:"Priya Raman",email:"priya.raman@example.com",phone:"212-555-0194",
    linkedin:"linkedin.com/in/priyaraman",currentLocation:"New York, NY",workAuth:"U.S. Citizen",
    education:[{school:"Rutgers University",degree:"BS",major:"Computer Science",start:"2015-09",end:"2019-05"}],
    experience:[{company:"FinCore",title:"Senior Software Engineer",start:"2019-07",end:"Present",current:true,
      description:"Built Java/Python microservices, Kafka pipelines, Spark jobs, Kubernetes deployments for fintech."}],
    skills:["Java","Python","Kubernetes","microservices","Kafka","Spark","some TensorFlow","AWS"],
    projects:[{name:"Feature Pipeline Modernization",description:"Designed Spark/Kafka workflows for ML-ready data.",tech:"Kafka, Spark, AWS"}],
    certifications:[{name:"AWS Solutions Architect",issuer:"AWS",date:"2024"}],
    cRole:"ML Platform Engineer, MLOps Engineer, Senior ML Engineer",
    cSkills:"Java, Python, Kubernetes, microservices, Kafka, Spark, some TensorFlow, AWS",
    cLocation:"NYC or remote, US only",cPreferences:"large companies, ML infrastructure",
    cSalary:200000,cEmpType:"Full-time",cVisa:"",
    dealbreakers:["No Junior Roles","No Startups"]
  },
  kenji:{
    name:"Kenji Nakamura",email:"kenji.nakamura@example.com",phone:"650-555-0151",
    linkedin:"linkedin.com/in/kenjinakamura",currentLocation:"Palo Alto, CA",workAuth:"F-1 (STEM OPT)",
    education:[{school:"Stanford University",degree:"MS",major:"Computer Science",start:"2024-09",end:"2026-06"}],
    experience:[{company:"VisionLab",title:"Graduate Researcher",start:"2024-09",end:"Present",current:true,
      description:"Published research in PyTorch-based NLP and computer vision. Authored 2 conference papers."}],
    skills:["Python","C++","deep learning","PyTorch","NLP","computer vision","published research"],
    projects:[{name:"Multimodal Research Prototype",description:"Published NLP and CV research at top venues.",tech:"Python, PyTorch, CUDA"}],
    certifications:[],
    cRole:"Research Scientist, ML Engineer, Applied Scientist, AI Engineer",
    cSkills:"Python, C++, deep learning, PyTorch, NLP, computer vision, published research",
    cLocation:"US only",cPreferences:"known H-1B sponsors, large tech, research labs",
    cSalary:120000,cEmpType:"Full-time",cVisa:"H-1B sponsorship required",
    dealbreakers:["No Contract Roles","No Temp Roles","Sponsorship Required"]
  }
};

const DEALBREAKER_OPTIONS = ["No Contract Roles","No Temp Roles","No Unpaid Roles","No Defense Companies","No Startups","No Senior Roles","No Staff Roles","No Junior Roles","No 3+ Years Required","No 5+ Years ML Required","Sponsorship Required"];
const PER_PAGE = 10;

// ─── State ────────────────────────────────────────────────────────────────────
const S = {
  profile: blankProfile(),
  dealbreakers: [],
  allJobs: [],
  page: 1,
  feedback: {},
  resumes: [],
  activeResume: null,   // unsaved generated resume (not yet in list)
  activeResumeId: null, // id of saved resume being viewed/edited
  masterResumeName: null,
  masterResumeText: null, // original PDF text for View Original
};

function blankProfile(){
  return {name:"",email:"",phone:"",linkedin:"",currentLocation:"",workAuth:"",
    education:[],experience:[],skills:[],projects:[],certifications:[]};
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const $=id=>document.getElementById(id);
const esc=v=>String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[c]);
const ea=v=>esc(v).replaceAll("\n"," ");

function toast(msg, type="success"){
  const t=$("toast");
  t.textContent=msg; t.className=`show ${type}`;
  clearTimeout(t._t); t._t=setTimeout(()=>t.className="",3000);
}

// ─── Navigation ───────────────────────────────────────────────────────────────
const PAGE_META = {
  profile: ["Your Profile","🔒 Your profile data is kept private and secure."],
  jobs: ["Jobs","Find the best opportunities that match your profile."],
  resume: ["Resume","Review and edit your AI-generated resume for the selected job."]
};

function navigate(p){
  document.querySelectorAll(".page").forEach(el=>el.classList.toggle("active",el.id===p+"Page"));
  document.querySelectorAll(".nav-btn").forEach(btn=>btn.classList.toggle("active",btn.dataset.page===p));
  $("pageTitle").textContent=PAGE_META[p][0];
  $("pageSubtitle").textContent=PAGE_META[p][1];
  if(p==="resume") renderResumes();
}

// ─── Init ─────────────────────────────────────────────────────────────────────
async function init(){
  buildDealbreakers();
  bindNav();
  bindProfile();
  bindJobs();
  bindResume();
  renderProfile();
  renderDefaultInsights();
  // Load real market insights from backend on startup
  try{
    const r=await fetch("/api/jobs/search",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({profile:{id:"default",name:"",skills:[],experience:[],education:[],projects:[],certifications:[]},
        criteria:{target_role:"",skills:[],location:"",salary_min:0,employment_type:"",visa_sponsorship:"",dealbreakers:[],limit:1}})});
    if(r.ok){
      const d=await r.json();
      if(d.market_insights) renderInsights(d.market_insights);
    }
  }catch(e){}
}

function buildDealbreakers(){
  const g=$("dbGrid"); g.innerHTML="";
  DEALBREAKER_OPTIONS.forEach(opt=>{
    const label=document.createElement("label");
    label.className="db-item";
    label.dataset.val=opt;
    const cb=document.createElement("input");
    cb.type="checkbox"; cb.value=opt;
    cb.addEventListener("change",()=>{
      label.classList.toggle("checked",cb.checked);
      if(cb.checked){if(!S.dealbreakers.includes(opt))S.dealbreakers.push(opt);}
      else S.dealbreakers=S.dealbreakers.filter(d=>d!==opt);
    });
    label.append(cb, document.createTextNode(" "+opt));
    g.append(label);
  });
}

function setDealbreakers(list){
  S.dealbreakers=[...list];
  $("dbGrid").querySelectorAll("input").forEach(cb=>{
    cb.checked=list.includes(cb.value);
    cb.closest(".db-item").classList.toggle("checked",cb.checked);
  });
}

function bindNav(){
  document.querySelectorAll(".nav-btn[data-page]").forEach(btn=>
    btn.addEventListener("click",()=>navigate(btn.dataset.page)));
}

function resetResumeState(){
  S.resumes=[];
  S.activeResume=null;
  S.activeResumeId=null;
  S.masterResumeName=null;
  S.masterResumeText=null;
  $("uploadLabel").textContent="Drag & drop your PDF resume here";
  $("uploadZone").classList.remove("has-file");
  $("masterResumeName").textContent="No resume uploaded";
  if($("viewOriginalBtn")) $("viewOriginalBtn").style.display="none";
  if($("versionsList")) $("versionsList").innerHTML="";
  if($("resumeCount")) $("resumeCount").textContent="0 saved";
  if($("resumeEmpty")) $("resumeEmpty").style.display="block";
  if($("resumeEditor")) $("resumeEditor").style.display="none";
}

// ─── Profile ──────────────────────────────────────────────────────────────────
function bindProfile(){
  // Persona select
  $("personaSelect").addEventListener("change",e=>{
    const key=e.target.value;
    if(key&&PERSONAS[key]){
      const p=PERSONAS[key];
      S.profile={name:p.name,email:p.email,phone:p.phone,linkedin:p.linkedin,
        currentLocation:p.currentLocation,workAuth:p.workAuth,
        education:[...p.education],experience:[...p.experience],
        skills:[...p.skills],projects:[...p.projects],certifications:[...(p.certifications||[])]};
      setDealbreakers(p.dealbreakers||[]);
      // Sync jobs filters from persona
      $("cRole").value=p.cRole||"";
      $("cSkills").value=p.cSkills||"";
      $("cLocation").value=p.cLocation||"";
      $("cPreferences").value=p.cPreferences||"";
      $("cSalary").value=p.cSalary||"";
      $("cEmpType").value=p.cEmpType||"Full-time";
      $("cVisa").value=p.cVisa||"";
      resetResumeState();
      renderProfile();
    } else {
      S.profile=blankProfile(); S.dealbreakers=[];
      setDealbreakers([]); renderProfile();
      $("cRole").value=""; $("cSkills").value=""; $("cLocation").value=""; $("cPreferences").value="";
      $("cSalary").value=""; $("cEmpType").value=""; $("cVisa").value="";
      resetResumeState();
    }
  });

  // PDF upload - fix double-trigger bug
  $("resumeFile").addEventListener("change",async e=>{
    const file=e.target.files[0]; if(!file) return;
    $("uploadLabel").textContent=file.name;
    $("uploadZone").classList.add("has-file");
    S.masterResumeName=file.name;
    $("masterResumeName").textContent=file.name;
    toast("Extracting resume...");
    try{
      const fd=new FormData(); fd.append("file",file);
      const res=await fetch("/api/profile/extract",{method:"POST",body:fd});
      if(!res.ok) throw new Error();
      const data=await res.json();
      // Store original text for View Original
      S.masterResumeText=data.raw_text||"";
      // Merge extracted into profile
      if(data.name) S.profile.name=data.name;
      if(data.email) S.profile.email=data.email;
      if(data.phone) S.profile.phone=data.phone;
      if(data.linkedin) S.profile.linkedin=data.linkedin;
      if(data.current_location) S.profile.currentLocation=data.current_location;
      if(data.work_authorization) S.profile.workAuth=data.work_authorization;
      if(data.education?.length) S.profile.education=data.education.map(e=>({school:e.school||"",degree:e.degree||"",major:e.major||"",start:e.start||"",end:e.end||""}));
      if(data.experience?.length) S.profile.experience=data.experience.map(e=>({company:e.company||"",title:e.title||"",start:e.start||"",end:e.end||"",current:Boolean(e.current),description:e.description||""}));
      if(data.skills?.length) S.profile.skills=data.skills;
      if(data.projects?.length) S.profile.projects=data.projects.map(p=>({name:p.name||"",description:p.description||"",tech:p.tech_stack||""}));
      if(data.certifications?.length) S.profile.certifications=data.certifications.map(c=>({name:c.name||"",issuer:c.issuer||"",date:c.date||""}));
      renderProfile();
      toast("✅ Resume extracted! Review and edit below.");
    }catch(err){
      console.warn("Extract failed:",err);
      toast("⚠️ Could not extract. Fill in manually.","error");
    }
  });
  $("uploadZone").addEventListener("click",e=>{
    if(e.target.tagName==="BUTTON"||e.target===($("resumeFile"))) return;
    $("resumeFile").click();
  });

  // Add buttons
  $("addEduBtn").addEventListener("click",()=>{S.profile.education.push({school:"",degree:"",major:"",start:"",end:""});renderEdu();});
  $("addExpBtn").addEventListener("click",()=>{S.profile.experience.push({company:"",title:"",start:"",end:"",current:false,description:""});renderExp();});
  $("addProjBtn").addEventListener("click",()=>{S.profile.projects.push({name:"",description:"",tech:""});renderProj();});
  $("addCertBtn").addEventListener("click",()=>{S.profile.certifications.push({name:"",issuer:"",date:""});renderCert();});

  // Skill input
  $("addSkillBtn").addEventListener("click",()=>{
    const row=$("skillInputRow");
    row.style.display=row.style.display==="none"?"flex":"none";
    if(row.style.display==="flex") $("skillInput").focus();
  });
  $("skillAddOk").addEventListener("click",addSkillFromInput);
  $("skillInput").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();addSkillFromInput();}if(e.key==="Escape"){$("skillInputRow").style.display="none";}});

  // Save buttons
  $("saveProfileBtn").addEventListener("click",async()=>{
    readFormIntoState(); await saveProfile(); toast("✅ Profile saved!");
  });
  $("goJobsBtn").addEventListener("click",async()=>{
    readFormIntoState(); await saveProfile(); syncFiltersFromProfile(); navigate("jobs"); findJobs();
  });
}

function addSkillFromInput(){
  const v=$("skillInput").value.trim(); if(!v) return;
  if(!S.profile.skills.includes(v)) S.profile.skills.push(v);
  $("skillInput").value=""; $("skillInputRow").style.display="none";
  renderSkills();
}

function syncFiltersFromProfile(){
  const p=S.profile;
  // Suggest target role from most recent job title
  if(!$("cRole").value){
    const lastJob=p.experience?.find(e=>e.current)||p.experience?.[0];
    if(lastJob?.title) $("cRole").value=lastJob.title;
  }
  if(!$("cSkills").value) $("cSkills").value=p.skills.slice(0,6).join(", ");
  if(!$("cLocation").value) $("cLocation").value=p.currentLocation||"";
  if(!$("cVisa").value) $("cVisa").value=(p.workAuth||"").includes("OPT")?"H-1B sponsorship required":"";
}

function renderProfile(){
  const p=S.profile;
  $("fName").value=p.name||""; $("fEmail").value=p.email||""; $("fPhone").value=p.phone||"";
  $("fLinkedin").value=p.linkedin||""; $("fLocation").value=p.currentLocation||"";
  $("fWorkAuth").value=p.workAuth||"";
  // Update avatar
  if(p.name){const parts=p.name.split(" ");$("avatarInitials").textContent=(parts[0]?.[0]||"")+(parts[1]?.[0]||"");$("accountName").textContent=p.name;}
  renderEdu(); renderExp(); renderSkills(); renderProj(); renderCert();
}

function renderEdu(){
  const l=$("eduList"); l.innerHTML="";
  if(!S.profile.education.length){l.innerHTML='<p class="empty-hint">No education added yet.</p>';return;}
  S.profile.education.forEach((item,i)=>{
    const d=document.createElement("div"); d.className="stack-card";
    d.innerHTML=`<div class="card-grid-3">
      <label>School<input data-edu="${i}" data-f="school" value="${ea(item.school)}"/></label>
      <label>Degree<input data-edu="${i}" data-f="degree" value="${ea(item.degree)}"/></label>
      <label>Major<input data-edu="${i}" data-f="major" value="${ea(item.major)}"/></label>
      <label>Start Date<input data-edu="${i}" data-f="start" value="${ea(item.start||"")}"/></label>
      <label>End Date (or Expected)<input data-edu="${i}" data-f="end" value="${ea(item.end||"")}"/></label>
    </div>
    <div class="card-actions"><button class="btn btn-danger btn-sm" data-del-edu="${i}">Delete</button></div>`;
    l.append(d);
  });
  l.querySelectorAll("[data-del-edu]").forEach(b=>b.addEventListener("click",()=>{S.profile.education.splice(+b.dataset.delEdu,1);renderEdu();}));
}

function renderExp(){
  const l=$("expList"); l.innerHTML="";
  if(!S.profile.experience.length){l.innerHTML='<p class="empty-hint">No work experience added yet.</p>';return;}
  S.profile.experience.forEach((item,i)=>{
    const cur=item.current||String(item.end||"").toLowerCase()==="present";
    const d=document.createElement("div"); d.className="stack-card";
    d.innerHTML=`<div class="card-grid-4">
      <label>Company<input data-exp="${i}" data-f="company" value="${ea(item.company)}"/></label>
      <label>Title<input data-exp="${i}" data-f="title" value="${ea(item.title)}"/></label>
      <label>Start Date<input data-exp="${i}" data-f="start" value="${ea(item.start)}"/></label>
      <label>End Date<input data-exp="${i}" data-f="end" value="${ea(item.end)}"/></label>
      <label class="field-full inline-check"><input data-exp="${i}" data-f="current" type="checkbox" ${cur?"checked":""}/> Current Role</label>
      <label class="field-full">Description<textarea data-exp="${i}" data-f="description" rows="2">${esc(item.description)}</textarea></label>
    </div>
    <div class="card-actions"><button class="btn btn-danger btn-sm" data-del-exp="${i}">Delete</button></div>`;
    l.append(d);
  });
  l.querySelectorAll("[data-del-exp]").forEach(b=>b.addEventListener("click",()=>{S.profile.experience.splice(+b.dataset.delExp,1);renderExp();}));
}

function renderSkills(){
  const tags=$("skillTags"); const empty=$("skillsEmpty");
  tags.innerHTML="";
  if(!S.profile.skills.length){empty.style.display="block";return;}
  empty.style.display="none";
  S.profile.skills.forEach(skill=>{
    const tag=document.createElement("span"); tag.className="tag";
    tag.innerHTML=`${esc(skill)} <button type="button">×</button>`;
    tag.querySelector("button").addEventListener("click",()=>{S.profile.skills=S.profile.skills.filter(s=>s!==skill);renderSkills();});
    tags.append(tag);
  });
}

function renderProj(){
  const l=$("projList"); l.innerHTML="";
  if(!S.profile.projects.length){l.innerHTML='<p class="empty-hint">No projects added yet.</p>';return;}
  S.profile.projects.forEach((item,i)=>{
    const d=document.createElement("div"); d.className="stack-card";
    d.innerHTML=`<div class="card-grid-3">
      <label>Project Name<input data-proj="${i}" data-f="name" value="${ea(item.name)}"/></label>
      <label class="field-full">Description<textarea data-proj="${i}" data-f="description" rows="2">${esc(item.description)}</textarea></label>
      <label>Tech Stack<input data-proj="${i}" data-f="tech" value="${ea(item.tech||"")}"/></label>
    </div>
    <div class="card-actions"><button class="btn btn-danger btn-sm" data-del-proj="${i}">Delete</button></div>`;
    l.append(d);
  });
  l.querySelectorAll("[data-del-proj]").forEach(b=>b.addEventListener("click",()=>{S.profile.projects.splice(+b.dataset.delProj,1);renderProj();}));
}

function renderCert(){
  const l=$("certList"); l.innerHTML="";
  if(!S.profile.certifications.length){l.innerHTML='<p class="empty-hint">No certifications added yet.</p>';return;}
  S.profile.certifications.forEach((item,i)=>{
    const d=document.createElement("div"); d.className="stack-card";
    d.innerHTML=`<div class="card-grid-3">
      <label>Certification Name<input data-cert="${i}" data-f="name" value="${ea(item.name)}"/></label>
      <label>Issuer<input data-cert="${i}" data-f="issuer" value="${ea(item.issuer||"")}"/></label>
      <label>Date<input data-cert="${i}" data-f="date" value="${ea(item.date||"")}"/></label>
    </div>
    <div class="card-actions"><button class="btn btn-danger btn-sm" data-del-cert="${i}">Delete</button></div>`;
    l.append(d);
  });
  l.querySelectorAll("[data-del-cert]").forEach(b=>b.addEventListener("click",()=>{S.profile.certifications.splice(+b.dataset.delCert,1);renderCert();}));
}

function readFormIntoState(){
  const p=S.profile;
  p.name=$("fName").value.trim(); p.email=$("fEmail").value.trim();
  p.phone=$("fPhone").value.trim(); p.linkedin=$("fLinkedin").value.trim();
  p.currentLocation=$("fLocation").value.trim(); p.workAuth=$("fWorkAuth").value;
  // Education
  p.education=[...document.querySelectorAll("[data-edu][data-f='school']")].map(inp=>{
    const i=inp.dataset.edu;
    return {school:inp.value.trim(),degree:document.querySelector(`[data-edu="${i}"][data-f="degree"]`).value.trim(),
      major:document.querySelector(`[data-edu="${i}"][data-f="major"]`).value.trim(),
      start:document.querySelector(`[data-edu="${i}"][data-f="start"]`).value.trim(),
      end:document.querySelector(`[data-edu="${i}"][data-f="end"]`).value.trim()};
  });
  // Experience
  p.experience=[...document.querySelectorAll("[data-exp][data-f='company']")].map(inp=>{
    const i=inp.dataset.exp;
    const cur=document.querySelector(`[data-exp="${i}"][data-f="current"]`).checked;
    return {company:inp.value.trim(),title:document.querySelector(`[data-exp="${i}"][data-f="title"]`).value.trim(),
      start:document.querySelector(`[data-exp="${i}"][data-f="start"]`).value.trim(),
      end:cur?"Present":document.querySelector(`[data-exp="${i}"][data-f="end"]`).value.trim(),
      current:cur,description:document.querySelector(`[data-exp="${i}"][data-f="description"]`).value.trim()};
  });
  // Projects
  p.projects=[...document.querySelectorAll("[data-proj][data-f='name']")].map(inp=>{
    const i=inp.dataset.proj;
    return {name:inp.value.trim(),description:document.querySelector(`[data-proj="${i}"][data-f="description"]`).value.trim(),
      tech:document.querySelector(`[data-proj="${i}"][data-f="tech"]`).value.trim()};
  });
  // Certifications
  p.certifications=[...document.querySelectorAll("[data-cert][data-f='name']")].map(inp=>{
    const i=inp.dataset.cert;
    return {name:inp.value.trim(),issuer:document.querySelector(`[data-cert="${i}"][data-f="issuer"]`).value.trim(),
      date:document.querySelector(`[data-cert="${i}"][data-f="date"]`).value.trim()};
  });
}

async function saveProfile(){
  try{
    const p=S.profile;
    await fetch("/api/profile/save",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({id:"default",name:p.name,email:p.email,phone:p.phone,
        linkedin:p.linkedin,current_location:p.currentLocation,work_authorization:p.workAuth,
        education:p.education,experience:p.experience,skills:p.skills,
        projects:p.projects.map(x=>({name:x.name,description:x.description,tech_stack:x.tech})),
        certifications:p.certifications})}).catch(()=>{});
  }catch(e){}
}

function toggleSection(id){ const el=$(id); if(el) el.style.display=el.style.display==="none"?"grid":"none"; }

// ─── Jobs ─────────────────────────────────────────────────────────────────────
function bindJobs(){
  $("findJobsBtn").addEventListener("click",findJobs);
  $("resetBtn").addEventListener("click",()=>{
    $("cRole").value=""; $("cSkills").value=""; $("cLocation").value=""; $("cPreferences").value="";
    $("cSalary").value=""; $("cEmpType").value=""; $("cVisa").value="";
    setDealbreakers([]); S.allJobs=[]; S.page=1; renderJobsPage();
  });
  $("dlMenuBtn").addEventListener("click",e=>{e.stopPropagation();$("dlMenu").classList.toggle("open");});
  document.addEventListener("click",()=>$("dlMenu").classList.remove("open"));
  $("dlMenu").querySelectorAll("button").forEach(btn=>btn.addEventListener("click",()=>exportJobs(btn.dataset.fmt)));
}

async function findJobs(){
  readFormIntoState();
  const btn=$("findJobsBtn"); btn.textContent="Ranking..."; btn.disabled=true;
  try{
    const payload={
      profile:{id:"default",name:S.profile.name,email:S.profile.email,
        current_location:S.profile.currentLocation,work_authorization:S.profile.workAuth,
        education:S.profile.education,experience:S.profile.experience,skills:S.profile.skills,
        projects:S.profile.projects.map(x=>({name:x.name,description:x.description,tech_stack:x.tech})),
        certifications:S.profile.certifications},
      criteria:{target_role:$("cRole").value.trim(),
        skills:$("cSkills").value.split(",").map(s=>s.trim()).filter(Boolean),
        location:$("cLocation").value.trim(),
        preferences:$("cPreferences").value.split(",").map(s=>s.trim()).filter(Boolean),
        salary_min:Number($("cSalary").value||0),
        employment_type:$("cEmpType").value||"",
        visa_sponsorship:$("cVisa").value||"",
        dealbreakers:S.dealbreakers,
        rejected_ids:Object.entries(S.feedback).filter(([,v])=>v===-1).map(([k])=>k),
        limit:50}
    };
    const res=await fetch("/api/jobs/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    if(!res.ok) throw new Error("Search failed: "+res.status);
    const data=await res.json();
    S.allJobs=data.results||[]; S.page=1;
    renderJobsPage();
    if(data.market_insights) renderInsights(data.market_insights);
    if(data.learned_preferences) renderLearned(data.learned_preferences);
    if(data.benchmark?.available) $("feedbackBadge").textContent=`Feedback NDCG@10: ${data.benchmark.ndcg_at_10}`;
    else if(data.benchmark) $("feedbackBadge").textContent=`Feedback NDCG: ${data.benchmark.message}`;
    else $("feedbackBadge").textContent="";
  }catch(err){
    console.error(err); toast("⚠️ Search failed. Is the backend running?","error");
  }finally{btn.textContent="🔍 Find Matching Jobs";btn.disabled=false;}
}

function renderJobsPage(){
  // Filter out rejected jobs from display
  const visibleJobs=S.allJobs.filter(j=>S.feedback[j.job_id||""]!==-1);
  const total=visibleJobs.length;
  const pages=Math.max(1,Math.ceil(total/PER_PAGE));
  if(S.page>pages) S.page=pages;
  const start=(S.page-1)*PER_PAGE;
  const slice=visibleJobs.slice(start,start+PER_PAGE);
  $("jobCount").textContent=total;
  const container=$("jobCards"); container.innerHTML="";
  if(!total){
    container.innerHTML='<div style="text-align:center;padding:60px 20px;color:var(--muted)"><p style="font-size:32px;margin-bottom:12px">🔍</p><p>No jobs found. Try adjusting your filters.</p></div>';
    $("paginationRow").style.display="none"; return;
  }
  slice.forEach(job=>container.append(makeCard(job)));
  // Pagination
  $("paginationRow").style.display="flex";
  $("pagInfo").textContent=`Showing ${start+1}–${Math.min(start+PER_PAGE,total)} of ${total} jobs`;
  const btns=$("pagBtns"); btns.innerHTML="";
  const addBtn=(lbl,p,active,disabled)=>{
    const b=document.createElement("button"); b.className="pg-btn"+(active?" active":""); b.textContent=lbl; b.disabled=!!disabled;
    b.addEventListener("click",()=>{S.page=p;renderJobsPage();window.scrollTo(0,300);});
    btns.append(b);
  };
  addBtn("‹",S.page-1,false,S.page===1);
  for(let p=1;p<=pages;p++){
    if(p===1||p===pages||Math.abs(p-S.page)<=1) addBtn(p,p,p===S.page);
    else if(Math.abs(p-S.page)===2){const sp=document.createElement("span");sp.textContent="…";sp.style.padding="0 4px";btns.append(sp);}
  }
  addBtn("›",S.page+1,false,S.page===pages);
}

function makeCard(job){
  const why=job.why_ranked_here||{};
  const jid=job.job_id||"";
  const fb=S.feedback[jid];
  const sal=job.salary_display||(job.salary_max>0?`$${job.salary_min?.toLocaleString()}–$${job.salary_max?.toLocaleString()}`:"Salary not listed");
  const card=document.createElement("div");
  let cardClass="job-card";
  if(fb===1) cardClass+=" accepted";
  if(fb===-1) cardClass+=" rejected";
  card.className=cardClass;
  const acceptStyle=fb===1?"background:var(--green);color:#fff;border-color:var(--green)":"color:var(--green-dark);border-color:#a7f3d0";
  const rejectStyle=fb===-1?"background:var(--red);color:#fff;border-color:var(--red)":"color:var(--red);border-color:var(--red-light)";
  card.innerHTML=`
    <div class="job-card-top">
      <div class="job-logo">${esc((job.company||"?")[0].toUpperCase())}</div>
      <div>
        <div class="job-title">${esc(job.title||"")}</div>
        <div class="job-co">${esc(job.company||"")} <span style="color:var(--green-dark);font-weight:700">✓</span></div>
        <div class="job-meta">
          <span>📍 ${esc(job.location||"nan")==="nan"?"Not specified":esc(job.location||"")}</span>
          <span>💼 ${esc(job.employment_type||"Full-time")}</span>
          <span>💰 ${esc(sal)}</span>
          ${job.link?`<span><a href="${ea(job.link)}" target="_blank" rel="noopener">🔗 Apply</a></span>`:""}
        </div>
      </div>
      <div class="score-circle">
        <strong>${job.match_score||0}%</strong>
        <small>Match</small>
      </div>
    </div>
    <div class="why-grid">
      <div class="why-item"><span class="wlabel">Skill Match</span><div class="wval">${why.skill_match||0}%</div></div>
      <div class="why-item"><span class="wlabel">Location Match</span><div class="wval">${why.location_match||0}%</div></div>
      <div class="why-item"><span class="wlabel">Salary Match</span><div class="wval">${why.salary_match||0}%</div></div>
      <div class="why-item"><span class="wlabel">Embedding Similarity</span><div class="wval">${why.embedding_similarity||0}%</div></div>
      <div class="why-item"><span class="wlabel">Experience Match</span><div class="wval">${why.experience_match||0}%</div></div>
      <div class="why-item"><span class="wlabel">Dealbreaker Check</span><div class="wval" style="color:var(--green-dark)">${why.dealbreaker_check||"Passed"}</div></div>
    </div>
    ${(job.missing_skills||[]).length?`<div class="missing">⚠️ Missing Skills: <strong>${job.missing_skills.map(esc).join(", ")}</strong></div>`:""}
    <div class="job-btns">
      <button class="btn btn-primary btn-sm gen-btn" data-jid="${ea(jid)}">📝 Generate Resume</button>
      <button class="btn btn-ghost btn-sm accept-btn" data-jid="${ea(jid)}" style="${acceptStyle}">✅ Accept</button>
      <button class="btn btn-ghost btn-sm reject-btn" data-jid="${ea(jid)}" style="${rejectStyle}">❌ Reject</button>
      <button class="btn btn-ghost btn-sm skip-btn" data-jid="${ea(jid)}" style="${fb===0?"color:var(--muted)":""}">⏭ Skip</button>
    </div>`;
  card.querySelector(".gen-btn").addEventListener("click",()=>generateResume(job));
  card.querySelector(".accept-btn").addEventListener("click",()=>sendFeedback(jid,"accept",job));
  card.querySelector(".reject-btn").addEventListener("click",()=>sendFeedback(jid,"reject",job));
  card.querySelector(".skip-btn").addEventListener("click",()=>sendFeedback(jid,"skip",job));
  return card;
}

async function sendFeedback(jid,action,job){
  S.feedback[jid]=action==="accept"?1:action==="reject"?-1:0;
  try{
    const res=await fetch("/api/feedback",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({profile_id:"default",job_id:jid,action})});
    if(res.ok){const d=await res.json();if(d.learned_preferences)renderLearned(d.learned_preferences);}
  }catch(e){}
  renderJobsPage();
}

function renderDefaultInsights(){
  renderBars("insSkills",[["Python",28],["SQL",24],["Machine Learning",12],["Data Analysis",10],["Excel",8],["Tableau",7],["AWS",6],["Java",5]]);
  renderBars("insRoles",[["Data Analyst",35],["Data Scientist",22],["ML Engineer",18],["Business Analyst",14],["Data Engineer",11]]);
  $("insSalary").innerHTML='<p style="font-size:12px;color:var(--muted);text-align:center;padding:16px 0">Run a search to see salary data</p>';
}

function renderInsights(ins){
  if(!ins) return;
  if(ins.top_skills?.length) renderBars("insSkills",ins.top_skills.map(([l,v])=>[l,Number(v)]));
  if(ins.in_demand_roles?.length) renderBars("insRoles",ins.in_demand_roles.map(([l,v])=>[l,Number(v)]));
  if(ins.salary_distribution?.length){
    // Use bar chart for salary too so labels show properly
    renderBars("insSalary",ins.salary_distribution.map(([l,v])=>[l,Number(v)]));
  }
}

function renderBars(id,rows){
  const mx=Math.max(...rows.map(([,v])=>v),1);
  $(id).innerHTML=rows.map(([l,v])=>`<div class="bar-row"><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(String(l))}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.round(v/mx*100)}%"></div></div><strong>${v}%</strong></div>`).join("");
}

function renderHistogram(id,[heights,labels]){
  $(id).innerHTML=`<div class="hist-bars">${heights.map(h=>`<div class="hist-bar" style="height:${h}%"></div>`).join("")}</div><div class="hist-labels">${labels.map(l=>`<span>${esc(l)}</span>`).join("")}</div>`;
}

function renderLearned(prefs){
  const c=$("insLearned"); if(!c) return;
  if(!prefs?.length){c.innerHTML='<p style="font-size:12px;color:var(--muted)">No feedback yet.</p>';return;}
  c.innerHTML=prefs.map(p=>`<div class="learned-item"><span>${esc(p.signal)}</span><strong>${p.weight>=0?"+":""}${p.weight}</strong></div>`).join("");
}

function exportJobs(fmt){
  if(!S.allJobs.length){toast("No jobs to export","error");return;}
  const rows=S.allJobs.slice(0,10).map(j=>({
    "Title":j.title,
    "Company":j.company,
    "Location":j.location,
    "Employment Type":j.employment_type||"Full-time",
    "Salary":j.salary_display||"Competitive",
    "Match Score":(j.match_score||0)+"%",
    "Apply Link":j.link||"",
    "Description":(j.description||"").slice(0,300)
  }));
  if(fmt==="json"){dlBlob("jobpilot_top10.json",JSON.stringify(rows,null,2),"application/json");return;}
  const csv="\uFEFF"+toCSV(rows);
  dlBlob("jobpilot_top10.csv",csv,"text/csv;charset=utf-8");
}

// ─── Resume ───────────────────────────────────────────────────────────────────
function bindResume(){
  $("saveResumeBtn").addEventListener("click",saveEdits);
  $("dlPdfBtn").addEventListener("click",()=>dlResume("pdf"));
  $("dlDocxBtn").addEventListener("click",()=>dlResume("docx"));
  $("viewOriginalBtn").addEventListener("click",()=>{
    if(!S.masterResumeName){toast("No resume uploaded","error");return;}
    const p=S.profile;
    // Build personal header
    const personal=`${p.name||""}\n${[p.email,p.phone,p.currentLocation,p.linkedin].filter(Boolean).join(" | ")}`;
    // Build experience text
    const experience=p.experience.map(e=>`${e.title} at ${e.company} (${e.start}–${e.end})\n${e.description||""}`).join("\n\n");
    // Build skills text
    const skills=p.skills.join(", ");
    // Build projects text
    const projects=p.projects.map(x=>`${x.name}: ${x.description}`).join("\n\n");
    const education=formatEducation(p.education);

    $("resumeEditorTitle").textContent=S.masterResumeName;
    $("resumeTargetJob").textContent="Original uploaded resume";
    $("resumeScore").textContent="--";
    const ph=$("edPersonal"); if(ph) ph.value=personal;
    $("edSummary").value="";
    if($("edEducation")) $("edEducation").value=education;
    $("edExperience").value=experience;
    $("edSkills").value=skills;
    $("edProjects").value=projects;
    $("aiChanges").innerHTML='<div class="ai-item">Showing original resume content</div>';
    $("resumeEmpty").style.display="none";
    $("resumeEditor").style.display="block";
    toast("Showing original resume");
  });
}

async function generateResume(job){
  readFormIntoState();
  const btn=document.querySelector(`.gen-btn[data-jid="${ea(job.job_id||"")}"]`);
  if(btn){btn.textContent="Generating...";btn.disabled=true;}
  const p=S.profile;
  const personalHeader=`${p.name||"Your Name"}\n${[p.email,p.phone,p.currentLocation,p.linkedin].filter(Boolean).join(" | ")}`;
  try{
    const res=await fetch("/api/resume/generate",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        profile:{id:"default",name:p.name,email:p.email,phone:p.phone,
          linkedin:p.linkedin,current_location:p.currentLocation,
          work_authorization:p.workAuth,education:p.education,
          experience:p.experience,skills:p.skills,
          projects:p.projects.map(x=>({name:x.name,description:x.description,tech_stack:x.tech})),
          certifications:p.certifications},
        job:{job_id:job.job_id,title:job.title,company:job.company,location:job.location,
          employment_type:job.employment_type,salary_min:job.salary_min,salary_max:job.salary_max,
          description:job.description,skills_extracted:job.skills_extracted,link:job.link}
      })});
    if(!res.ok) throw new Error();
    const data=await res.json();
    S.activeResume={id:data.id,name:data.name,jobTitle:data.job_title||job.title,
      company:data.company||job.company,matchScore:job.match_score||null,
      created:new Date().toISOString().slice(0,10),personalHeader,
      summary:data.summary||"",skills:data.skills||"",experience:data.experience||"",
      education:data.education||formatEducation(p.education),
      projects:data.projects||"",aiChanges:data.ai_changes||[]};
    navigate("resume");
    toast("✅ Resume generated! Edit and click Save when ready.");
  }catch(err){
    console.warn("Generate failed:",err);
    const rel=p.skills.filter(s=>(job.skills_extracted||[]).map(x=>x.toLowerCase()).includes(s.toLowerCase()));
    S.activeResume={id:`r${Date.now()}`,
      name:`Resume_${(job.title||"").replaceAll(" ","_")}_${(job.company||"").replaceAll(" ","_")}`,
      jobTitle:job.title,company:job.company,matchScore:job.match_score||null,
      created:new Date().toISOString().slice(0,10),personalHeader,
      summary:`${p.name} targeting ${job.title} roles at ${job.company}, with strengths in ${(rel.length?rel:p.skills).slice(0,4).join(", ")}.`,
      education:formatEducation(p.education),
      skills:(rel.length?rel:p.skills).join(", "),
      experience:p.experience.map(e=>`${e.title} at ${e.company} (${e.start}–${e.end})\n${e.description}`).join("\n\n"),
      projects:p.projects.map(x=>`${x.name}: ${x.description}`).join("\n\n"),
      aiChanges:["Highlighted relevant skills","Tailored summary to target role"]};
    navigate("resume");
    toast("Resume generated. Edit and click Save when ready.");
  }finally{
    if(btn){btn.textContent="📝 Generate Resume";btn.disabled=false;}
  }
}

function renderResumes(){
  $("masterResumeName").textContent=S.masterResumeName||"No resume uploaded";
  $("viewOriginalBtn").style.display=S.masterResumeName?"inline-flex":"none";
  const hasActive=!!S.activeResume;
  const hasSaved=S.resumes.length>0;
  if(!hasActive&&!hasSaved){
    $("resumeEmpty").style.display="block";
    $("resumeEditor").style.display="none";
    return;
  }
  $("resumeEmpty").style.display="none";
  $("resumeEditor").style.display="block";
  $("resumeCount").textContent=`${S.resumes.length} saved`;
  if(hasActive) openResumeObj(S.activeResume);
  else if(hasSaved) openResume(S.resumes[0].id);
  renderVersions();
}

function openResumeObj(r){
  if(!r) return;
  $("resumeEditorTitle").textContent=r.name;
  $("resumeTargetJob").textContent=`${r.jobTitle} · ${r.company}`;
  $("resumeScore").textContent=r.matchScore?`${r.matchScore}%`:"--";
  const ph=$("edPersonal"); if(ph) ph.value=r.personalHeader||"";
  $("edSummary").value=r.summary||"";
  if($("edEducation")) $("edEducation").value=r.education||"";
  $("edExperience").value=r.experience||"";
  $("edSkills").value=r.skills||""; $("edProjects").value=r.projects||"";
  $("aiChanges").innerHTML=(r.aiChanges||[]).map(c=>`<div class="ai-item">${esc(c)}</div>`).join("")||'<div class="ai-item">Resume tailored to job description</div>';
}

function openResume(id){
  const r=S.resumes.find(x=>x.id===id); if(!r) return;
  S.activeResume=null; // viewing saved version, not unsaved draft
  S.activeResumeId=id;
  openResumeObj(r);
}

function renderVersions(){
  const l=$("versionsList"); l.innerHTML="";
  if(!S.resumes.length){
    l.innerHTML='<p style="color:var(--muted);font-size:13px;padding:12px 0">No saved resumes yet. Generate and save a resume to see it here.</p>';
    return;
  }
  S.resumes.forEach(r=>{
    const row=document.createElement("div"); row.className="version-row";
    row.innerHTML=`<div class="version-name">${esc(r.name)}</div>
      <div class="version-meta">${esc(r.jobTitle)} @ ${esc(r.company)}</div>
      <div class="version-meta">${esc(r.created)}</div>
      <div class="version-btns">
        <button class="btn btn-ghost btn-sm" data-edit="${r.id}">View / Edit</button>
        <button class="btn btn-ghost btn-sm" data-dlr="${r.id}" data-fmt="pdf">PDF</button>
        <button class="btn btn-ghost btn-sm" data-dlr="${r.id}" data-fmt="docx">DOCX</button>
        <button class="btn btn-danger btn-sm" data-del="${r.id}">Delete</button>
      </div>`;
    l.append(row);
  });
  l.querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>openResume(b.dataset.edit)));
  l.querySelectorAll("[data-dlr]").forEach(b=>b.addEventListener("click",()=>dlResumeById(b.dataset.dlr,b.dataset.fmt)));
  l.querySelectorAll("[data-del]").forEach(b=>b.addEventListener("click",()=>{
    S.resumes=S.resumes.filter(r=>r.id!==b.dataset.del);
    if(S.activeResumeId===b.dataset.del) S.activeResumeId=null;
    renderResumes();
  }));
}

function saveEdits(){
  // Read current editor values
  const ph=$("edPersonal"); 
  const updated={
    personalHeader: ph?ph.value:"",
    summary:$("edSummary").value,
    education:$("edEducation")?$("edEducation").value:"",
    experience:$("edExperience").value,
    skills:$("edSkills").value,
    projects:$("edProjects").value,
  };
  if(S.activeResume){
    // Save unsaved draft to list
    const r={...S.activeResume,...updated};
    S.resumes.unshift(r);
    S.activeResumeId=r.id;
    S.activeResume=null;
    $("resumeCount").textContent=`${S.resumes.length} saved`;
    renderVersions();
    toast("✅ Resume saved!");
  } else if(S.activeResumeId){
    // Update existing saved resume
    const r=S.resumes.find(x=>x.id===S.activeResumeId);
    if(r) Object.assign(r,updated);
    renderVersions();
    toast("✅ Resume updated!");
  }
}

function dlResume(fmt){
  const r=S.activeResume||(S.activeResumeId?S.resumes.find(x=>x.id===S.activeResumeId):null);
  if(r) dlResumeById(r,fmt);
}

function dlResumeById(rOrId,fmt){
  const r=typeof rOrId==="string"?S.resumes.find(x=>x.id===rOrId):rOrId;
  if(!r) return;
  if(fmt==="docx"){dlBlob(`${r.name}.docx`,mkDocx(r),"application/vnd.openxmlformats-officedocument.wordprocessingml.document");return;}
  dlBlob(`${r.name}.pdf`,mkResumePdf(r),"application/pdf");
}

function formatEducation(items){
  return (items||[]).map(e=>{
    const degree=[e.degree,e.major].filter(Boolean).join(" ");
    const dates=[e.start,e.end].filter(Boolean).join("-");
    return [e.school,degree,dates].filter(Boolean).join(" | ");
  }).filter(Boolean).join("\n");
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function toCSV(rows){
  if(!rows.length) return "";
  const h=Object.keys(rows[0]);
  return[h.join(","),...rows.map(r=>h.map(k=>`"${String(r[k]||"").replaceAll('"','""')}"`).join(","))].join("\n");
}
function dlBlob(name,content,type){
  const blob=content instanceof Blob?content:new Blob([content],{type});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download=name;a.click();URL.revokeObjectURL(url);
}

// Proper single-page resume PDF with name, contact, sections
function mkResumePdf(r){
  const plines=(r.personalHeader||"").split("\n");
  const nm=plines[0]||"";
  const contact=plines[1]||"";
  const W=612, H=792, ML=72, MR=72, textW=W-ML-MR;
  let stream="";
  let y=740;

  // Name - large bold
  stream+=`BT\n/Hb 20 Tf\n${ML} ${y} Td\n(${pesc(nm)}) Tj\nET\n`;
  y-=26;
  // Contact line
  if(contact){
    stream+=`BT\n/H 10 Tf\n0.4 0.4 0.4 rg\n${ML} ${y} Td\n(${pesc(contact)}) Tj\nET\n`;
    y-=14;
  }
  // Green divider
  stream+=`0.02 0.47 0.34 RG\n1.5 w\n${ML} ${y} m\n${W-MR} ${y} l\nS\n0 0 0 RG\n0 w\n`;
  y-=16;

  const sections=[
    {title:"SUMMARY",content:r.summary},
    {title:"EDUCATION",content:r.education},
    {title:"EXPERIENCE",content:r.experience},
    {title:"SKILLS",content:r.skills},
    {title:"PROJECTS",content:r.projects},
  ];
  sections.forEach(({title,content})=>{
    if(!content?.trim()||y<80) return;
    y-=8;
    stream+=`BT\n/Hb 10 Tf\n0.02 0.47 0.34 rg\n${ML} ${y} Td\n(${pesc(title)}) Tj\nET\n`;
    y-=14;
    content.split("\n").forEach(line=>{
      if(y<60) return;
      const wrapped=wrapLine(line.trim(),textW,5.8);
      wrapped.forEach(wl=>{
        if(y<60) return;
        stream+=`BT\n/H 10 Tf\n0 0 0 rg\n${ML} ${y} Td\n(${pesc(wl)}) Tj\nET\n`;
        y-=14;
      });
      if(!line.trim()) y-=4;
    });
  });

  const streamBytes=new TextEncoder().encode(stream);
  const objs=[
    `1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n`,
    `2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n`,
    `3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${W} ${H}] /Resources << /Font << /H 4 0 R /Hb 5 0 R >> >> /Contents 6 0 R >>\nendobj\n`,
    `4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n`,
    `5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n`,
  ];
  const contentObj=`6 0 obj\n<< /Length ${streamBytes.length} >>\nstream\n${stream}\nendstream\nendobj\n`;
  objs.push(contentObj);
  let pdf="%PDF-1.4\n";const offs=[0];
  objs.forEach(o=>{offs.push(pdf.length);pdf+=o;});
  const xr=pdf.length;
  pdf+=`xref\n0 ${objs.length+1}\n0000000000 65535 f \n`;
  offs.slice(1).forEach(o=>{pdf+=`${String(o).padStart(10,"0")} 00000 n \n`;});
  pdf+=`trailer\n<< /Size ${objs.length+1} /Root 1 0 R >>\nstartxref\n${xr}\n%%EOF`;
  return new Blob([pdf],{type:"application/pdf"});
}

function wrapLine(line,maxPts,charW){
  const max=Math.floor(maxPts/charW);
  if(!line) return [""];
  if(line.length<=max) return [line];
  const words=line.split(" ");const rows=[];let cur="";
  words.forEach(w=>{const n=cur?`${cur} ${w}`:w;if(n.length>max&&cur){rows.push(cur);cur=w;}else cur=n;});
  if(cur) rows.push(cur);
  return rows.length?rows:[""];
}

// DOCX with proper formatting
function mkDocx(r){
  const boldPara=(text,sz=28)=>`<w:p><w:pPr><w:spacing w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="${sz}"/></w:rPr><w:t xml:space="preserve">${xesc(text)}</w:t></w:r></w:p>`;
  const colorTitle=(text)=>`<w:p><w:pPr><w:spacing w:before="160" w:after="60"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="047857"/><w:sz w:val="20"/></w:rPr><w:t>${xesc(text)}</w:t></w:r></w:p>`;
  const normal=(text)=>`<w:p><w:pPr><w:spacing w:after="40"/></w:pPr><w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">${xesc(text)}</w:t></w:r></w:p>`;
  const hr=`<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="047857"/></w:pBdr><w:spacing w:after="80"/></w:pPr></w:p>`;
  const plines=(r.personalHeader||"").split("\n");
  let body=boldPara(plines[0]||r.name||"",32);
  if(plines[1]) body+=normal(plines[1]);
  body+=hr;
  const addSec=(title,content)=>{
    if(!content?.trim()) return;
    body+=colorTitle(title);
    content.split("\n").forEach(l=>{body+=normal(l);});
  };
  addSec("SUMMARY",r.summary);
  addSec("EDUCATION",r.education);
  addSec("EXPERIENCE",r.experience);
  addSec("SKILLS",r.skills);
  addSec("PROJECTS",r.projects);
  const doc=`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080"/></w:sectPr></w:body></w:document>`;
  const files={
    "[Content_Types].xml":`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`,
    "_rels/.rels":`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`,
    "word/document.xml":doc
  };
  return new Blob([mkZip(files)],{type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document"});
}
function pesc(v){return String(v).replace(/[^\x20-\x7E]/g,"?").replaceAll("\\","\\\\").replaceAll("(","\\(").replaceAll(")","\\)");}
function xesc(v){return String(v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&apos;"})[c]);}
function wrap(line,max){if(!line)return[""];const words=line.split(" ");const rows=[];let cur="";words.forEach(w=>{const n=cur?`${cur} ${w}`:w;if(n.length>max&&cur){rows.push(cur);cur=w;}else cur=n;});if(cur)rows.push(cur);return rows;}
function mkZip(files){const enc=new TextEncoder();const local=[];const central=[];let off=0;Object.entries(files).forEach(([name,content])=>{const nb=enc.encode(name),cb=enc.encode(content),crc=crc32(cb);const lh=zh(0x04034b50,[[20,2],[0,2],[0,2],[0,2],[0,2],[crc,4],[cb.length,4],[cb.length,4],[nb.length,2],[0,2]]);local.push(lh,nb,cb);const ch=zh(0x02014b50,[[20,2],[20,2],[0,2],[0,2],[0,2],[0,2],[crc,4],[cb.length,4],[cb.length,4],[nb.length,2],[0,2],[0,2],[0,2],[0,2],[0,4],[off,4]]);central.push(ch,nb);off+=lh.length+nb.length+cb.length;});const cs=central.reduce((s,p)=>s+p.length,0);const end=zh(0x06054b50,[[0,2],[0,2],[Object.keys(files).length,2],[Object.keys(files).length,2],[cs,4],[off,4],[0,2]]);return cat([...local,...central,end]);}
function zh(sig,fields){const len=4+fields.reduce((s,[,sz])=>s+sz,0);const b=new Uint8Array(len);const v=new DataView(b.buffer);v.setUint32(0,sig,true);let o=4;fields.forEach(([val,sz])=>{if(sz===2)v.setUint16(o,val,true);if(sz===4)v.setUint32(o,val>>>0,true);o+=sz;});return b;}
function cat(parts){const t=parts.reduce((s,p)=>s+p.length,0);const o=new Uint8Array(t);let off=0;parts.forEach(p=>{o.set(p,off);off+=p.length;});return o;}
function crc32(bytes){let c=0xffffffff;for(const b of bytes){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^(0xedb88320&-(c&1));}return(c^0xffffffff)>>>0;}

init();
