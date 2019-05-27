let requestbutton = document.getElementById("request");
let constractbutton = document.getElementById("contract");
let cancelbutton = document.getElementById("cancel");
let submitbutton = document.getElementById("submit");
let request_list = document.getElementById("request-form").getElementsByTagName("select")
let contract_list = document.getElementById("contract-form").getElementsByTagName("select")



function toggle_window(){
  document.getElementById("window").classList.toggle("hidden-item")
  request_list[1].selectedIndex = 0
  request_list[0].selectedIndex = 0
  contract_list[0].selectedIndex = 0
  contract_list[1].selectedIndex = 0
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
    body : JSON.stringify({name: request_list[0].value})}).then(function(response){
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
  console.log(request_list[1].selectedIndex,contract_list[1].selectedIndex)
  if (request_list[1].selectedIndex + contract_list[1].selectedIndex == 0){
    console.log("pass")
  }else if(request_list[1].selectedIndex * contract_list[1].selectedIndex != 0){
    console.log("pass")
  }else if(request_list[1].selectedIndex != 0){
    //代行依頼送信
    send_request()
  }else if(contract_list[1].selectedIndex != 0){
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
    request_list[0].appendChild(temp_option.cloneNode(true))
    temp_option = document.createElement('option')
    temp_option.textContent = json[item];
    contract_list[0].appendChild(temp_option.cloneNode(true))
  }
})

submitbutton.addEventListener("click",send_date,false)

request_list[0].addEventListener("change",function(){
  //子要素を全て削除
  for(var item in [...Array(request_list[1].children.length).keys()]){
    console.log(item)
    if(item != 0){
      request_list[1].removeChild(request_list[1].children[1])
    }
  }
  fetch("_get_of_member",{method:"post",headers : { "content-type" : "application/json; charset=utf-8" },
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
