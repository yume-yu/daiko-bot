let requestbutton = document.getElementById("request");
let constractbutton = document.getElementById("constract");
let select_list_name = document.getElementById("requestWindow").getElementsByTagName("select")
requestbutton.addEventListener("click",function(){
  document.getElementById("requestWindow").classList.toggle("hidden-item")
},false)
fetch("_get_members").then(function(response){
  return response.json();
}).then(function(json){
  for(var item in json){
    var temp_option = document.createElement('option')
    temp_option.textContent = json[item];
    select_list_name[0].appendChild(temp_option)
  }
})
