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
select_list_name[0].addEventListener("change",function(){
  //子要素を全て削除
  for(var item in [...Array(select_list_name[1].children.length).keys()]){
    console.log(item)
    if(item != 0){
        select_list_name[1].removeChild(select_list_name[1].children[1])
    }
  }
  fetch("_get_of_member",{method:"POST",headers : { "Content-type" : "application/json; charset=utf-8" },
    body : JSON.stringify({name: select_list_name[0].value})}).then(function(response){
      return response.json()
    }).then(function(json){
      console.log(json)
      for(var item in json){
        // console.log(Object.keys(json[item]))
        // console.log(json[item])
        for(var time in item){
          //console.log(json[item][Object.keys(json[item])][time])
          var temp_option = document.createElement('option')
          temp_option.textContent = Object.keys(json[item]) + ":" + json[item][Object.keys(json[item])][time]["start"] + "~" + json[item][Object.keys(json[item])][time]["end"]
          temp_option.value = item+ ":" + time
          select_list_name[1].appendChild(temp_option)
        }
      }
    })
})
