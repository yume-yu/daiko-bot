let requestbutton = document.getElementById("request");
let constractbutton = document.getElementById("contract");
let cancelbutton = document.getElementById("cancel");
let request_list = document.getElementById("request-form").getElementsByTagName("select")
let contract_list = document.getElementById("contract-form").getElementsByTagName("select")

function toggle_window(){
  document.getElementById("window").classList.toggle("hidden-item")
  request_list[1].selectedIndex = 0
  request_list[0].selectedIndex = 0
  contract_list[0].selectedIndex = 0
}

function active_request(){
  toggle_window()
  document.getElementById("request-form").classList.remove("hidden-item")
  document.getElementById("contract-form").classList.add("hidden-item")
}

function active_contract(){
  toggle_window()
  document.getElementById("request-form").classList.add("hidden-item")
  document.getElementById("contract-form").classList.remove("hidden-item")
}

requestbutton.addEventListener("click",active_request,false)
constractbutton.addEventListener("click",active_contract,false)
cancelbutton.addEventListener("click",toggle_window,false)

fetch("_get_members").then(function(response){
  return response.json();
}).then(function(json){
  for(var item in json){
    var temp_option = document.createElement('option')
    temp_option.textContent = json[item];
    request_list[0].appendChild(temp_option)
  }
})
request_list[0].addEventListener("change",function(){
  //子要素を全て削除
  for(var item in [...Array(request_list[1].children.length).keys()]){
    console.log(item)
    if(item != 0){
        request_list[1].removeChild(request_list[1].children[1])
    }
  }
  fetch("_get_of_member",{method:"POST",headers : { "Content-type" : "application/json; charset=utf-8" },
    body : JSON.stringify({name: request_list[0].value})}).then(function(response){
      return response.json()
    }).then(function(json){
      console.log(json)
      for(var item in json){
        // console.log(Object.keys(json[item]))
        // console.log(json[item])
        for(var time in json[item][Object.keys(json[item])]){
          //console.log(json[item][Object.keys(json[item])][time])
          var temp_option = document.createElement('option')
          console.log(Object.keys(json[item]) + ":" + json[item][Object.keys(json[item])][time]["start"] + "~" + json[item][Object.keys(json[item])][time]["end"])
          temp_option.textContent = Object.keys(json[item]) + ":" + json[item][Object.keys(json[item])][time]["start"] + "~" + json[item][Object.keys(json[item])][time]["end"]
          temp_option.value = item+ ":" + time
          request_list[1].appendChild(temp_option)
        }
      }
    })
})
