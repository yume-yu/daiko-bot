let requestbutton = document.getElementById("request");
let constractbutton = document.getElementById("contract");
let cancelbutton = document.getElementById("cancel");
let submitbutton = document.getElementById("submit");
let request_list = document.getElementById("request-form").getElementsByTagName("select")
let contract_list = document.getElementById("contract-form").getElementsByTagName("select")



function toggle_window(){
  document.getElementById("window").classList.toggle("hidden-item")
  request_list._shift.selectedIndex = 0
  request_list._name.selectedIndex = 0
  contract_list._yourname.selectedIndex = 0
  contract_list._requested.selectedIndex = 0
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

function send_request(){
  fetch("_get_of_member",{method:"post",headers : { "content-type" : "application/json; charset=utf-8" },
    body : JSON.stringify({name: request_list._name.value})}).then(function(response){
      return response.json()
    }).then(function(json){
      let shift = json
      console.log(shift)
      date  = JSON.stringify(
        {
          day:Object.keys(json[request_list._shift.value.split(":")[0]])[0],
          name:request_list._name.value,
          index:Number(request_list._shift.value.split(":")[1]) + 1,
        }
      )
      console.log(date)
      fetch("request",{method:"post",headers : { "content-type" : "application/json; charset=utf-8" },
        body : date}).then(function(response){
          return response.json()
        }).then(function(json){
          // console.log(json)
          toggle_window()
          fetch("update_image").then(function(response){return response.text()}).then(function(text){document.getElementsByTagName("img")[0].src = text;console.log(text)})

        })
    })
}
function send_contract(){
  fetch("_get_of_member",{method:"post",headers : { "content-type" : "application/json; charset=utf-8" },
    body : json.stringify({name: request_list[0].value})}).then(function(response){
      return response.json()
    }).then(function(json){
    })
}

function send_date(){
  if (request_list._shift.selectedIndex + contract_list._yourname.selectedIndex == 0){
    console.log("pass")
  }else if(request_list._shift.selectedIndex * contract_list._yourname.selectedIndex != 0){
    console.log("pass")
  }else if(request_list._shift.selectedIndex != 0){
    //代行依頼送信
    send_request()
  }else if(contract_list._yourname.selectedIndex != 0){
    send_contract()
  }
}

requestbutton.addEventListener("click",active_request,false)
constractbutton.addEventListener("click",active_contract,false)
cancelbutton.addEventListener("click",toggle_window,false)

let members_json;
fetch("_get_members").then(function(response){
  return response.json();
}).then(function(json){
  members_json = json
  for(var item in json){
    var temp_option = document.createElement('option')
    temp_option.textContent = json[item];
    request_list._name.appendChild(temp_option.cloneNode(true))
    temp_option = document.createElement('option')
    temp_option.textContent = json[item];
    contract_list._yourname.appendChild(temp_option.cloneNode(true))
  }
})

fetch("_get_requested").then(function(response){
  return response.json();
}).then(function(json){
  for(var item in json){
    var temp_option = document.createElement('option')
    console.log(json[item])
    temp_option.textContent = Object.keys(json[item]) + ":" + json[item][Object.keys(json[item])]["start"] + "~" + json[item][Object.keys(json[item])]["end"]
    temp_option.value = item
    contract_list._requested.appendChild(temp_option)
  }
})

submitbutton.addEventListener("click",send_date,false)

request_list._name.addEventListener("change",function(){
  //子要素を全て削除
  for(var item in [...Array(request_list._shift.children.length).keys()]){
    console.log(item)
    if(item != 0){
      request_list._shift.removeChild(request_list._shift.children[1])
    }
  }
  fetch("_get_of_member",{method:"post",headers : { "content-type" : "application/json; charset=utf-8" },
    body : JSON.stringify({name: request_list._name.value})}).then(function(response){
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
          request_list._shift.appendChild(temp_option)
        }
      }
    })
})
